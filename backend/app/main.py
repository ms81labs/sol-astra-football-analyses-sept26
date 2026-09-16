from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
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
from .llm import run_analysis
from .report_export import build_match_report_export
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
    untrusted_model_output,
    upload_quota,
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
from .workbench.contracts import SourceClockIdentity, unknown_metric
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
from .workbench.dossier import http_dossier
from .workbench.evaluation import (
    analyst_workflow_measures,
    current_repository_evaluation_gate,
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
    Label,
    PreprocessorAdapter,
    TrackerAdapter,
    merge_tiled_detections,
    preview_identity_change,
    score_detections,
    score_detections_by_stratum,
    separate_ball_states,
    tile_to_source,
)
from .workbench.quantities import pitch_axes, split_scores, transform_legacy_display
from .workbench.recovery import full_disk, recovery_objectives, support_bundle, unresolved_incidents
from .workbench.repository import RepositoryAdapter, http_may_run_gpu, vector_broker_required
from .workbench.reports import held_out_questions
from .workbench.research import execute_track, may_write_product_paths, research_lane
from .workbench.retention import PROTECTED, may_delete
from .workbench.media import (
    DecodedFrame,
    SamplingAudit,
    apply_crop_and_rotation,
    align_clip_start_to_grid,
    colour_round_trip,
    cpu_fallback,
    decode_memory_policy,
    detect_camera_cuts,
    four_rates_receipt,
    frame_interval_for_target_fps,
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
from .workbench.rights import rights_register
from .workbench.risks import independent_reviewer, risk_register, worked_match_flow
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
        source_sha256="0" * 64,
        weights="unpromoted",
        configuration="evidence_v1",
        hardware="cpu",
        native_builds=[],
        selected_backend="opencv+ultralytics_track",
        frame_count=0,
        call_count=0,
        cold_timing_ms=0.0,
        warm_timing_ms=0.0,
        peak_memory_bytes=0,
        transferred_bytes=0,
        output_quality="unproven",
        accepted_coverage=0.0,
        failure_cases=["labels_incomplete"],
        allocated_spend=0.0,
        fallback_event="cpu_local",
    )


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


def build_match_bundle(storage: Storage, match_id: str) -> dict[str, object]:
    from .match_bundle import build_match_bundle as assemble_match_bundle

    return assemble_match_bundle(storage, match_id)


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


def _dashboard_metric_measured(summary: dict, metric: str) -> bool:
    records = summary.get("metricAvailability") or []
    record = next((item for item in records if item.get("metric") == metric), None)
    if record is None:
        return True
    return record.get("availability") in {"available", "experimental"}


def _dashboard_average(summaries: list[dict], *, field: str, metric: str) -> float | None:
    values = [
        float(summary.get(field, 0) or 0)
        for summary in summaries
        if _dashboard_metric_measured(summary, metric)
    ]
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def create_app(
    storage_root: Path | str | None = None,
    run_jobs_inline: bool = False,
    settings: ProcessingSettings | None = None,
) -> FastAPI:
    settings = settings or ProcessingSettings.from_env()
    storage = Storage(_resolve_storage_root(storage_root))
    runner = JobRunner(storage.storage_root, run_jobs_inline=run_jobs_inline, settings=settings)

    app = FastAPI(title="Guerilla Analytics API", version="0.1.0")
    app.state.storage = storage
    app.state.runner = runner
    app.include_router(create_workbench_router(storage.storage_root))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.trusted_frontend_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Idempotency-Key", "Authorization", "X-Object-Scope", "X-Deployment-Boundary", "X-Tenant-Id"],
    )
    app.add_middleware(BrowserOriginMiddleware, trusted_origins=settings.trusted_frontend_origins)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"], www_redirect=False)

    def _external_soccernet_ui_binding_root() -> Path:
        return storage.storage_root / EXTERNAL_SOCCERNET_UI_BINDING_DIR

    def _load_external_soccernet_view_model() -> dict:
        view_model_path = _external_soccernet_ui_binding_root() / "analysis_product_ui_view_model.json"
        if not view_model_path.exists():
            raise HTTPException(status_code=404, detail="SoccerNet analysis product UI binding not ready")
        return json.loads(view_model_path.read_text(encoding="utf-8"))

    def _external_soccertrack_match_bundle_bridge_root() -> Path:
        return storage.storage_root / EXTERNAL_SOCCERTRACK_MATCH_BUNDLE_BRIDGE_DIR

    def _load_external_soccertrack_match_bundle(match_id: str) -> dict:
        bundle_path = _external_soccertrack_match_bundle_bridge_root() / "soccertrack_external_match_bundle.json"
        if not bundle_path.exists():
            raise HTTPException(status_code=404, detail="SoccerTrack external match bundle bridge not ready")
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        expected_match_ids = {match_id, f"soccertrack:{match_id}"}
        bundle_match = bundle.get("match") if isinstance(bundle.get("match"), dict) else {}
        provenance = bundle.get("provenance") if isinstance(bundle.get("provenance"), dict) else {}
        actual_match_ids = {
            str(bundle_match.get("id") or ""),
            str(provenance.get("externalSourceMatchId") or ""),
        }
        if not expected_match_ids.intersection(actual_match_ids):
            raise HTTPException(status_code=404, detail="SoccerTrack external match bundle not found")
        if bundle.get("schemaVersion") != "match_bundle_v1":
            raise HTTPException(status_code=409, detail="SoccerTrack external match bundle contract invalid")
        return bundle

    def _external_soccertrack_ui_binding_root() -> Path:
        return storage.storage_root / EXTERNAL_SOCCERTRACK_UI_BINDING_DIR

    def _external_benchmark_ui_binding_root() -> Path:
        return storage.storage_root / EXTERNAL_BENCHMARK_UI_BINDING_DIR

    def _external_benchmark_decision_surface_root() -> Path:
        return storage.storage_root / EXTERNAL_BENCHMARK_DECISION_SURFACE_DIR

    def _video_to_analysis_finish_line_binding_root() -> Path:
        return storage.storage_root / VIDEO_TO_ANALYSIS_FINISH_LINE_PRODUCT_BINDING_DIR

    def _video_to_analysis_acceptance_report_binding_root() -> Path:
        return storage.storage_root / VIDEO_TO_ANALYSIS_ACCEPTANCE_REPORT_BINDING_DIR

    def _video_to_analysis_operator_handoff_binding_root() -> Path:
        return storage.storage_root / VIDEO_TO_ANALYSIS_OPERATOR_HANDOFF_BINDING_DIR

    def _video_to_analysis_release_readout_binding_root() -> Path:
        return storage.storage_root / VIDEO_TO_ANALYSIS_RELEASE_READOUT_BINDING_DIR

    def _video_to_analysis_post_release_monitoring_binding_root() -> Path:
        return storage.storage_root / VIDEO_TO_ANALYSIS_POST_RELEASE_MONITORING_BINDING_DIR

    def _video_to_analysis_detector_evaluation_report_binding_root() -> Path:
        return storage.storage_root / VIDEO_TO_ANALYSIS_DETECTOR_EVALUATION_REPORT_BINDING_DIR

    def _video_to_analysis_promotion_review_report_binding_root() -> Path:
        return storage.storage_root / VIDEO_TO_ANALYSIS_PROMOTION_REVIEW_REPORT_BINDING_DIR

    def _video_to_analysis_promoted_runtime_monitoring_binding_root() -> Path:
        return storage.storage_root / VIDEO_TO_ANALYSIS_PROMOTED_RUNTIME_MONITORING_BINDING_DIR

    def _video_to_analysis_operator_dashboard_binding_root() -> Path:
        return storage.storage_root / VIDEO_TO_ANALYSIS_OPERATOR_DASHBOARD_BINDING_DIR

    def _video_to_analysis_real_video_scaleout_report_binding_root() -> Path:
        fixed_root = storage.storage_root / VIDEO_TO_ANALYSIS_REAL_VIDEO_SCALEOUT_REPORT_BINDING_DIR
        candidate_root = fixed_root.parent
        dirs = [
            path
            for path in candidate_root.glob("video_to_analysis_real_video_scaleout_report_route_binding_v*")
            if path.is_dir()
            and (path / "real_video_scaleout_report_view_model.json").exists()
            and (path / "real_video_scaleout_report_route_contract.json").exists()
        ]
        if not dirs:
            return fixed_root
        return max(dirs, key=lambda path: int(path.name.rsplit("_v", 1)[-1]))

    def _video_to_analysis_bounded_next_sample_report_binding_root() -> Path:
        fixed_root = storage.storage_root / VIDEO_TO_ANALYSIS_BOUNDED_NEXT_SAMPLE_REPORT_BINDING_DIR
        candidate_root = fixed_root.parent
        dirs = [
            path
            for path in candidate_root.glob("video_to_analysis_bounded_next_sample_report_route_binding_v*")
            if path.is_dir()
            and (path / "bounded_next_sample_report_view_model.json").exists()
            and (path / "bounded_next_sample_report_route_contract.json").exists()
        ]
        if not dirs:
            return fixed_root
        return max(dirs, key=lambda path: int(path.name.rsplit("_v", 1)[-1]))

    def _load_external_benchmark_view_model() -> dict:
        binding_root = _external_benchmark_ui_binding_root()
        view_model_path = binding_root / "external_benchmark_product_ui_view_model.json"
        contract_path = binding_root / "external_benchmark_product_ui_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="External benchmark product UI binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/external/benchmark/report":
            raise HTTPException(status_code=409, detail="External benchmark product UI route contract invalid")
        if route_contract.get("htmlRoutePath") != "/external/benchmark/report":
            raise HTTPException(status_code=409, detail="External benchmark product UI route contract invalid")
        if view_model.get("schemaVersion") != "football_external_benchmark_product_ui_view_model_v1":
            raise HTTPException(status_code=409, detail="External benchmark product UI binding contract invalid")
        return view_model

    def _load_external_benchmark_report_html() -> str:
        _load_external_benchmark_view_model()
        html_path = _external_benchmark_ui_binding_root() / "external_benchmark_product_ui_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="External benchmark product UI binding not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_external_benchmark_decision_view_model() -> dict:
        surface_root = _external_benchmark_decision_surface_root()
        view_model_path = surface_root / "product_decision_surface_view_model.json"
        contract_path = surface_root / "product_decision_surface_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="External benchmark decision surface not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/external/benchmark/decision":
            raise HTTPException(status_code=409, detail="External benchmark decision surface route contract invalid")
        if route_contract.get("htmlRoutePath") != "/external/benchmark/decision":
            raise HTTPException(status_code=409, detail="External benchmark decision surface route contract invalid")
        if view_model.get("schemaVersion") != "external_benchmark_product_decision_surface_view_model_v1":
            raise HTTPException(status_code=409, detail="External benchmark decision surface contract invalid")
        return view_model

    def _load_external_benchmark_decision_html() -> str:
        _load_external_benchmark_decision_view_model()
        html_path = _external_benchmark_decision_surface_root() / "product_decision_surface_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="External benchmark decision surface not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_finish_line_view_model() -> dict:
        binding_root = _video_to_analysis_finish_line_binding_root()
        view_model_path = binding_root / "finish_line_product_view_model.json"
        contract_path = binding_root / "finish_line_product_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis finish-line binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/finish-line":
            raise HTTPException(status_code=409, detail="Video-to-analysis finish-line route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/finish-line":
            raise HTTPException(status_code=409, detail="Video-to-analysis finish-line route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_finish_line_product_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis finish-line binding contract invalid")
        return view_model

    def _load_video_to_analysis_finish_line_html() -> str:
        _load_video_to_analysis_finish_line_view_model()
        html_path = _video_to_analysis_finish_line_binding_root() / "finish_line_product_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis finish-line HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_acceptance_report_view_model() -> dict:
        binding_root = _video_to_analysis_acceptance_report_binding_root()
        view_model_path = binding_root / "acceptance_report_view_model.json"
        contract_path = binding_root / "acceptance_report_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis acceptance report binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/acceptance-report":
            raise HTTPException(status_code=409, detail="Video-to-analysis acceptance report route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/acceptance-report":
            raise HTTPException(status_code=409, detail="Video-to-analysis acceptance report route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_acceptance_report_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis acceptance report binding contract invalid")
        return view_model

    def _load_video_to_analysis_acceptance_report_html() -> str:
        _load_video_to_analysis_acceptance_report_view_model()
        html_path = _video_to_analysis_acceptance_report_binding_root() / "acceptance_report_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis acceptance report HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_operator_handoff_view_model() -> dict:
        binding_root = _video_to_analysis_operator_handoff_binding_root()
        view_model_path = binding_root / "operator_handoff_view_model.json"
        contract_path = binding_root / "operator_handoff_bound_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis operator handoff binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/operator-handoff":
            raise HTTPException(status_code=409, detail="Video-to-analysis operator handoff route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/operator-handoff":
            raise HTTPException(status_code=409, detail="Video-to-analysis operator handoff route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_operator_handoff_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis operator handoff binding contract invalid")
        return view_model

    def _load_video_to_analysis_operator_handoff_html() -> str:
        _load_video_to_analysis_operator_handoff_view_model()
        html_path = _video_to_analysis_operator_handoff_binding_root() / "operator_handoff_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis operator handoff HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_release_readout_view_model() -> dict:
        binding_root = _video_to_analysis_release_readout_binding_root()
        view_model_path = binding_root / "release_readout_view_model.json"
        contract_path = binding_root / "release_readout_bound_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis release readout binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/release-readout":
            raise HTTPException(status_code=409, detail="Video-to-analysis release readout route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/release-readout":
            raise HTTPException(status_code=409, detail="Video-to-analysis release readout route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_release_readout_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis release readout binding contract invalid")
        return view_model

    def _load_video_to_analysis_release_readout_html() -> str:
        _load_video_to_analysis_release_readout_view_model()
        html_path = _video_to_analysis_release_readout_binding_root() / "release_readout_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis release readout HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_post_release_monitoring_view_model() -> dict:
        binding_root = _video_to_analysis_post_release_monitoring_binding_root()
        view_model_path = binding_root / "post_release_monitoring_view_model.json"
        contract_path = binding_root / "post_release_monitoring_bound_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis post-release monitoring binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/post-release-monitoring":
            raise HTTPException(status_code=409, detail="Video-to-analysis post-release monitoring route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/post-release-monitoring":
            raise HTTPException(status_code=409, detail="Video-to-analysis post-release monitoring route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_post_release_monitoring_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis post-release monitoring binding contract invalid")
        return view_model

    def _load_video_to_analysis_post_release_monitoring_html() -> str:
        _load_video_to_analysis_post_release_monitoring_view_model()
        html_path = _video_to_analysis_post_release_monitoring_binding_root() / "post_release_monitoring_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis post-release monitoring HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_detector_evaluation_report_view_model() -> dict:
        binding_root = _video_to_analysis_detector_evaluation_report_binding_root()
        view_model_path = binding_root / "detector_evaluation_report_view_model.json"
        contract_path = binding_root / "detector_evaluation_report_bound_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis detector evaluation report binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/detector-evaluation-report":
            raise HTTPException(status_code=409, detail="Video-to-analysis detector evaluation report route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/detector-evaluation-report":
            raise HTTPException(status_code=409, detail="Video-to-analysis detector evaluation report route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_detector_evaluation_report_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis detector evaluation report binding contract invalid")
        return view_model

    def _load_video_to_analysis_detector_evaluation_report_html() -> str:
        _load_video_to_analysis_detector_evaluation_report_view_model()
        html_path = _video_to_analysis_detector_evaluation_report_binding_root() / "detector_evaluation_report_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis detector evaluation report HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_promotion_review_report_view_model() -> dict:
        binding_root = _video_to_analysis_promotion_review_report_binding_root()
        view_model_path = binding_root / "promotion_review_report_view_model.json"
        contract_path = binding_root / "promotion_review_report_bound_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis promotion review report binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/promotion-review":
            raise HTTPException(status_code=409, detail="Video-to-analysis promotion review route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/promotion-review":
            raise HTTPException(status_code=409, detail="Video-to-analysis promotion review route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_promotion_review_report_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis promotion review binding contract invalid")
        return view_model

    def _load_video_to_analysis_promotion_review_report_html() -> str:
        _load_video_to_analysis_promotion_review_report_view_model()
        html_path = _video_to_analysis_promotion_review_report_binding_root() / "promotion_review_report_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis promotion review HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_promoted_runtime_monitoring_view_model() -> dict:
        binding_root = _video_to_analysis_promoted_runtime_monitoring_binding_root()
        view_model_path = binding_root / "promoted_runtime_monitoring_view_model.json"
        contract_path = binding_root / "promoted_runtime_monitoring_bound_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis promoted runtime monitoring binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/promoted-runtime-monitoring":
            raise HTTPException(status_code=409, detail="Video-to-analysis promoted runtime monitoring route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/promoted-runtime-monitoring":
            raise HTTPException(status_code=409, detail="Video-to-analysis promoted runtime monitoring route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_promoted_runtime_monitoring_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis promoted runtime monitoring binding contract invalid")
        return view_model

    def _load_video_to_analysis_promoted_runtime_monitoring_html() -> str:
        _load_video_to_analysis_promoted_runtime_monitoring_view_model()
        html_path = _video_to_analysis_promoted_runtime_monitoring_binding_root() / "promoted_runtime_monitoring_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis promoted runtime monitoring HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_operator_dashboard_view_model() -> dict:
        binding_root = _video_to_analysis_operator_dashboard_binding_root()
        view_model_path = binding_root / "operator_dashboard_view_model.json"
        contract_path = binding_root / "operator_dashboard_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis operator dashboard binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/operator-dashboard":
            raise HTTPException(status_code=409, detail="Video-to-analysis operator dashboard route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/operator-dashboard":
            raise HTTPException(status_code=409, detail="Video-to-analysis operator dashboard route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_operator_dashboard_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis operator dashboard binding contract invalid")
        return view_model

    def _load_video_to_analysis_operator_dashboard_html() -> str:
        _load_video_to_analysis_operator_dashboard_view_model()
        html_path = _video_to_analysis_operator_dashboard_binding_root() / "operator_dashboard_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis operator dashboard HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_real_video_scaleout_report_view_model() -> dict:
        binding_root = _video_to_analysis_real_video_scaleout_report_binding_root()
        view_model_path = binding_root / "real_video_scaleout_report_view_model.json"
        contract_path = binding_root / "real_video_scaleout_report_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis real-video scaleout report binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/real-video-scaleout-report":
            raise HTTPException(status_code=409, detail="Video-to-analysis real-video scaleout report route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/real-video-scaleout-report":
            raise HTTPException(status_code=409, detail="Video-to-analysis real-video scaleout report route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_real_video_scaleout_report_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis real-video scaleout report binding contract invalid")
        return view_model

    def _load_video_to_analysis_real_video_scaleout_report_html() -> str:
        _load_video_to_analysis_real_video_scaleout_report_view_model()
        html_path = _video_to_analysis_real_video_scaleout_report_binding_root() / "real_video_scaleout_report_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis real-video scaleout report HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_bounded_next_sample_report_view_model() -> dict:
        binding_root = _video_to_analysis_bounded_next_sample_report_binding_root()
        view_model_path = binding_root / "bounded_next_sample_report_view_model.json"
        contract_path = binding_root / "bounded_next_sample_report_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis bounded next-sample report binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/bounded-next-sample-report":
            raise HTTPException(status_code=409, detail="Video-to-analysis bounded next-sample report route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/bounded-next-sample-report":
            raise HTTPException(status_code=409, detail="Video-to-analysis bounded next-sample report route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_bounded_next_sample_report_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis bounded next-sample report binding contract invalid")
        return view_model

    def _load_video_to_analysis_bounded_next_sample_report_html() -> str:
        _load_video_to_analysis_bounded_next_sample_report_view_model()
        html_path = _video_to_analysis_bounded_next_sample_report_binding_root() / "bounded_next_sample_report_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis bounded next-sample report HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_external_soccertrack_view_model(match_id: str) -> dict:
        binding_root = _external_soccertrack_ui_binding_root()
        view_model_path = binding_root / "analysis_product_ui_view_model.json"
        contract_path = binding_root / "analysis_product_ui_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="SoccerTrack analysis product UI binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        allowed_paths = {
            route_contract.get("apiRoutePath"),
            route_contract.get("routePath"),
        }
        expected_paths = {
            f"/api/external/soccertrack/{match_id}/analysis",
            f"/external/soccertrack/{match_id}/analysis",
        }
        if not allowed_paths.intersection(expected_paths):
            raise HTTPException(status_code=404, detail="SoccerTrack analysis product UI binding not found")
        if view_model.get("schemaVersion") != "soccertrack_analysis_product_ui_view_model_v1":
            raise HTTPException(status_code=409, detail="SoccerTrack analysis product UI binding contract invalid")
        return view_model

    def _load_external_soccertrack_analysis_html(match_id: str) -> str:
        _load_external_soccertrack_view_model(match_id)
        html_path = _external_soccertrack_ui_binding_root() / "analysis_product_ui_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="SoccerTrack analysis product UI binding not ready")
        return html_path.read_text(encoding="utf-8")

    @app.get("/api/external/soccernet/full-analysis")
    def get_external_soccernet_full_analysis() -> dict:
        return _load_external_soccernet_view_model()

    @app.get("/external/soccernet/full-analysis")
    def get_external_soccernet_full_analysis_page() -> HTMLResponse:
        html_path = _external_soccernet_ui_binding_root() / "analysis_product_ui_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="SoccerNet analysis product UI binding not ready")
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

    @app.get("/api/external/soccertrack/{match_id}/export/match.json")
    def export_external_soccertrack_match_json(match_id: str) -> dict:
        return _load_external_soccertrack_match_bundle(match_id)

    @app.get("/api/external/soccertrack/{match_id}/analysis")
    def get_external_soccertrack_analysis(match_id: str) -> dict:
        return _load_external_soccertrack_view_model(match_id)

    @app.get("/external/soccertrack/{match_id}/analysis")
    def get_external_soccertrack_analysis_page(match_id: str) -> HTMLResponse:
        return HTMLResponse(content=_load_external_soccertrack_analysis_html(match_id))

    @app.get("/api/external/benchmark/report")
    def get_external_benchmark_report() -> dict:
        return _load_external_benchmark_view_model()

    @app.get("/external/benchmark/report")
    def get_external_benchmark_report_page() -> HTMLResponse:
        return HTMLResponse(content=_load_external_benchmark_report_html())

    @app.get("/api/external/benchmark/decision")
    def get_external_benchmark_decision_surface() -> dict:
        return _load_external_benchmark_decision_view_model()

    @app.get("/external/benchmark/decision")
    def get_external_benchmark_decision_surface_page() -> HTMLResponse:
        return HTMLResponse(content=_load_external_benchmark_decision_html())

    @app.get("/api/video-to-analysis/finish-line")
    def get_video_to_analysis_finish_line() -> dict:
        return _load_video_to_analysis_finish_line_view_model()

    @app.get("/video-to-analysis/finish-line")
    def get_video_to_analysis_finish_line_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_finish_line_html())

    @app.get("/api/video-to-analysis/acceptance-report")
    def get_video_to_analysis_acceptance_report() -> dict:
        return _load_video_to_analysis_acceptance_report_view_model()

    @app.get("/video-to-analysis/acceptance-report")
    def get_video_to_analysis_acceptance_report_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_acceptance_report_html())

    @app.get("/api/video-to-analysis/operator-handoff")
    def get_video_to_analysis_operator_handoff() -> dict:
        return _load_video_to_analysis_operator_handoff_view_model()

    @app.get("/video-to-analysis/operator-handoff")
    def get_video_to_analysis_operator_handoff_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_operator_handoff_html())

    @app.get("/api/video-to-analysis/release-readout")
    def get_video_to_analysis_release_readout() -> dict:
        return _load_video_to_analysis_release_readout_view_model()

    @app.get("/video-to-analysis/release-readout")
    def get_video_to_analysis_release_readout_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_release_readout_html())

    @app.get("/api/video-to-analysis/post-release-monitoring")
    def get_video_to_analysis_post_release_monitoring() -> dict:
        return _load_video_to_analysis_post_release_monitoring_view_model()

    @app.get("/video-to-analysis/post-release-monitoring")
    def get_video_to_analysis_post_release_monitoring_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_post_release_monitoring_html())

    @app.get("/api/video-to-analysis/detector-evaluation-report")
    def get_video_to_analysis_detector_evaluation_report() -> dict:
        return _load_video_to_analysis_detector_evaluation_report_view_model()

    @app.get("/video-to-analysis/detector-evaluation-report")
    def get_video_to_analysis_detector_evaluation_report_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_detector_evaluation_report_html())

    @app.get("/api/video-to-analysis/promotion-review")
    def get_video_to_analysis_promotion_review_report() -> dict:
        return _load_video_to_analysis_promotion_review_report_view_model()

    @app.get("/video-to-analysis/promotion-review")
    def get_video_to_analysis_promotion_review_report_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_promotion_review_report_html())

    @app.get("/api/video-to-analysis/promoted-runtime-monitoring")
    def get_video_to_analysis_promoted_runtime_monitoring() -> dict:
        return _load_video_to_analysis_promoted_runtime_monitoring_view_model()

    @app.get("/video-to-analysis/promoted-runtime-monitoring")
    def get_video_to_analysis_promoted_runtime_monitoring_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_promoted_runtime_monitoring_html())

    @app.get("/api/video-to-analysis/operator-dashboard")
    def get_video_to_analysis_operator_dashboard() -> dict:
        return _load_video_to_analysis_operator_dashboard_view_model()

    @app.get("/video-to-analysis/operator-dashboard")
    def get_video_to_analysis_operator_dashboard_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_operator_dashboard_html())

    @app.get("/api/video-to-analysis/real-video-scaleout-report")
    def get_video_to_analysis_real_video_scaleout_report() -> dict:
        return _load_video_to_analysis_real_video_scaleout_report_view_model()

    @app.get("/video-to-analysis/real-video-scaleout-report")
    def get_video_to_analysis_real_video_scaleout_report_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_real_video_scaleout_report_html())

    @app.get("/api/video-to-analysis/bounded-next-sample-report")
    def get_video_to_analysis_bounded_next_sample_report() -> dict:
        return _load_video_to_analysis_bounded_next_sample_report_view_model()

    @app.get("/video-to-analysis/bounded-next-sample-report")
    def get_video_to_analysis_bounded_next_sample_report_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_bounded_next_sample_report_html())

    @app.post("/api/matches", status_code=202)
    async def create_match(
        name: str = Form(...),
        inputMode: str = Form(...),
        config: str = Form("{}"),
        file: UploadFile = File(...),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict:
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
            runner.admit(job.id, match_id=match.id, source_sha256=storage.source_sha256(match.id), budget=0.0)
        except ValueError:
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
            runner.ledger.timeout_before_response(job_id)
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
            runner.ledger.lost_connection(job_id)
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

    @app.get("/api/evaluation/measures")
    def get_evaluation_measures() -> dict:
        return evaluation_measures()

    @app.get("/api/evaluation/workflow")
    def get_evaluation_workflow() -> dict:
        return analyst_workflow_measures()

    @app.post("/api/evaluation/workflow")
    def post_evaluation_workflow(payload: dict | None = None) -> dict:
        del payload
        return analyst_workflow_measures()

    @app.get("/api/evaluation/protocol")
    def get_evaluation_protocol() -> dict:
        return current_repository_evaluation_gate().model_dump(mode="json")

    @app.post("/api/evaluation/protocol")
    def post_evaluation_protocol(payload: dict | None = None) -> dict:
        del payload
        return current_repository_evaluation_gate().model_dump(mode="json")

    @app.get("/api/research/lane")
    def get_research_lane() -> dict:
        return research_lane()

    @app.post("/api/research/tracks/{track_id:path}/execute")
    def post_research_track(track_id: str) -> dict:
        if track_id.endswith("/execute"):
            track_id = track_id[: -len("/execute")]
        return execute_track(track_id, in_production=True)

    @app.post("/api/rollback")
    def post_rollback(payload: dict | None = None) -> dict:
        body = payload or {}
        return rollback_release(
            flag_name=str(body.get("flagName") or "unspecified"),
            affected_outputs=list(body.get("affectedOutputs") or []),
        )

    @app.get("/api/xt")
    def get_xt() -> dict:
        return xt_deferred_plan()

    @app.get("/api/credits")
    def get_credits() -> dict:
        return credit_allocation()

    @app.get("/api/admission/{profile}")
    def get_admission(profile: str) -> dict:
        try:
            return admit_camera(profile).model_dump(mode="json")  # type: ignore[arg-type]
        except KeyError as exc:
            raise HTTPException(status_code=400, detail="Unknown camera profile") from exc

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

    @app.get("/api/training/drills")
    def get_training_drills() -> dict:
        return drill_library()

    @app.get("/api/rights")
    def get_rights() -> dict:
        return rights_register()

    @app.get("/api/roster")
    def get_roster() -> dict:
        return {"items": model_roster()}

    @app.get("/api/roster/labels")
    def get_roster_labels() -> dict:
        return label_products()

    @app.get("/api/roster/video")
    def get_roster_video() -> dict:
        return video_model_roster()

    @app.get("/api/roster/frontier")
    def get_roster_frontier() -> dict:
        return frontier_provider_role(model_id="unspecified")

    @app.get("/api/roster/promotion/{task}")
    def get_roster_promotion(task: str) -> dict:
        return promotion_gate(task=task, independent_accepted=False, licence_recorded=False)

    @app.post("/api/roster/promotion/{task}")
    def post_roster_promotion(task: str, payload: dict | None = None) -> dict:
        del payload
        return promotion_gate(task=task, independent_accepted=False, licence_recorded=False)

    @app.get("/api/risks")
    def get_risks() -> dict:
        return {"items": risk_register()}

    @app.get("/api/milestones")
    def get_milestones() -> dict:
        return {
            "items": milestone_plan(),
            "owners": owners(),
            "progress": progress_signal(
                completed_analyst_tasks=0,
                validated_capability_gates=0,
                merged_files=0,
            ),
        }

    @app.get("/api/targets")
    def get_targets() -> dict:
        return metadata_api_targets()

    @app.get("/api/decisions")
    def get_decisions() -> dict:
        return {"items": architecture_decisions()}

    @app.get("/api/residency")
    def get_residency() -> dict:
        return residency_claim(requested_region="eu", provider="daytona")

    @app.get("/api/broker")
    def get_broker() -> dict:
        return distributed_broker(measured_workload_needs=False)

    @app.get("/api/vector")
    def get_vector() -> dict:
        return vector_database(measured_recall_benefit=False)

    @app.get("/api/deployment/{mode}")
    def get_deployment_mode(mode: str) -> dict:
        try:
            return deployment_mode(mode)
        except KeyError as exc:
            raise HTTPException(status_code=400, detail="Unknown deployment mode") from exc

    @app.get("/api/recovery")
    def get_recovery() -> dict:
        return {
            "deletion": access_deletion_procedure(requested=False, controller_recorded=False),
            "unresolvedIncidents": unresolved_incidents(),
            "recoveryObjectives": recovery_objectives(data_volume_measured=False, disruption_measured=False),
            "stalePermissions": {
                "stale": True,
                "admitted": False,
                "reasonCodes": ["PERMISSION_EXPIRY_UNRECORDED"],
            },
        }

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

    @app.get("/api/scale/{matches}")
    def get_scale_scenario(matches: int) -> dict:
        payload = dict(scale_scenario(matches_per_month=matches))
        payload["gbEqualsGiB"] = False
        payload["decimalGb"] = 5.4
        payload["gib"] = decimal_gb_to_gib(5.4)
        return payload

    @app.get("/api/privacy/dpia")
    def get_privacy_dpia() -> dict:
        return dpia_screen(
            youth_footage=False,
            identifiable_faces=True,
            cloud_requested=False,
            cloud_permitted=False,
        ).model_dump(mode="json")

    @app.get("/api/gpu")
    def get_gpu() -> dict:
        capability = probe_gpu()
        payload = capability.model_dump(mode="json")
        payload["canPromoteDefault"] = False
        payload["videoEngine"] = cuda_visibility_is_not_video_capability(cuda_visible=capability.available)
        return payload

    @app.get("/api/native")
    def get_native() -> dict:
        gate = native_gate(repo_root=Path.cwd(), approval_env=dict(os.environ))
        return {
            **gate.model_dump(mode="json"),
            "pinned": pinned_native_artifacts(),
            "osProfiles": qualified_os_profiles(profile="ubuntu"),
            "ffmpeg": ffmpeg_build_review(),
            "rpcFleet": no_rpc_fleet(),
            "customNative": custom_native_justification(measured_savings=False, required_capability=False),
        }

    @app.get("/api/security")
    def get_security(x_deployment_boundary: str | None = Header(default=None)) -> dict:
        bound = (x_deployment_boundary or "loopback").lower()
        return {
            "modelOutput": untrusted_model_output(
                claimed_actions=[],
                allowed_actions=frozenset({"open_interval", "draft_report"}),
                evidence_ids=[],
                known_ids=set(),
            ),
            "publicExposure": public_exposure_gate(security_review_accepted=False, bound=bound),
            "encryption": deployment_encryption(boundary=bound),
            "allowlist": protocol_network_allowlist(url="http://127.0.0.1/"),
            "decoder": constrained_decoder(argv=["ffmpeg", "-i", "local.mp4"], network_enabled=False),
            "storage": least_privilege_storage(credential_scope="object"),
            "secretsAdmitted": secrets_in_artifacts("cleanupResult=unknown")["admitted"],
            "signedJobAccess": signed_scoped_job_access(token=None, job_id="job-1", token_job_id=None),
            "egress": egress_policy(destination="https://evil.example", authorised_hosts=frozenset()),
        }

    @app.get("/api/assistance")
    def get_assistance() -> dict:
        fallback = providers_disabled_fallback(metrics=[], events=[])
        return {
            **fallback,
            "providersEnabled": False,
            "budgets": dual_budgets(vision=2.0, language=0.1),
            "embeddings": embeddings_retrieve("", passages=[]),
            "escalation": escalation_requires_quality_gap(model_uncertain=True, measured_gap=False),
        }

    @app.get("/api/decode/memory")
    def get_decode_memory() -> dict:
        gpu = probe_gpu()
        return decode_memory_policy(
            mode="offline",
            hardware_decode_ok=False,
            cuda_visible=gpu.available,
            video_engine_capability=False,
        )

    @app.get("/api/reviewer")
    def get_reviewer() -> dict:
        return independent_reviewer(developer="unrecorded", reviewer="unrecorded", inspected_held_out=False)

    @app.get("/api/flow")
    def get_worked_flow() -> dict:
        return worked_match_flow()

    @app.get("/api/identity")
    def get_identity_policy() -> dict:
        payload = reconnect_across_cut(cut_detected=False)
        payload["appearance"] = appearance_embedding_policy()
        payload["faceRecognition"] = face_recognition(requested=False)
        payload["crossSeasonIdentity"] = cross_season_identity(requested=False)
        payload["candidateRejoin"] = candidate_rejoin()
        return payload

    @app.get("/api/incidents/ladder")
    def get_incident_ladder() -> dict:
        return {
            "level2": level2_schematic_replay(coordinates=[]),
            "level3": level3_multiview(),
            "vlm": vlm_confidence_is_not_referee(confidence=0.99),
            "replay": broadcast_replay_not_simultaneous(same_timestamp=False),
            "homography": elevated_body_part_homography(part="foot"),
            "invisible": invisible_entity_not_repaired_by_larger_model(visible=False),
        }

    @app.get("/api/evaluation/hota")
    def get_evaluation_hota() -> dict:
        return score_hota_idf1(
            label_space="official_pitch",
            hand_edited_summary=False,
            native_predictions_present=False,
        )

    @app.get("/api/shots/tree")
    def get_shot_tree() -> dict:
        return {
            "tree": tree_challenger(logistic_calibrated=False),
            "temporal": learned_temporal(labelled_errors_justify=False),
        }

    @app.get("/api/collaboration")
    def get_collaboration() -> dict:
        return {
            "local": collaboration_lock(mode="local_only"),
            "hosted": collaboration_lock(mode="hosted_collaboration", lock_holder="analyst-a", requester="analyst-b"),
        }

    @app.get("/api/media/stride")
    def get_media_stride() -> dict:
        return vid_stride_policy()

    @app.get("/api/cache/tenancy")
    def get_cache_tenancy() -> dict:
        return {
            "crossTenant": cross_tenant_cache_reuse(
                source_tenant="loopback",
                requester_tenant="other",
                explicit_privacy_design=False,
            ),
            "columnar": columnar_observation_store(),
        }

    @app.get("/api/quantities/axes")
    def get_pitch_axes() -> dict:
        return pitch_axes()

    @app.get("/api/timing/gpu")
    def get_gpu_timing() -> dict:
        return gpu_timing_scope(submission_ms=0.0, completed_ms=None, device_aware=False)

    @app.get("/api/native/memory")
    def get_native_memory() -> dict:
        return quantized_weight_memory(weight_bytes=0)

    @app.get("/api/capacity")
    def get_capacity() -> dict:
        return historical_capacity_seconds()

    @app.get("/api/repository")
    def get_repository() -> dict:
        return {
            "httpMayRunGpu": http_may_run_gpu(),
            "vectorBrokerRequired": vector_broker_required(),
            "replacesStorageModule": RepositoryAdapter.replaces_storage_module,
            "backendName": RepositoryAdapter.backend_name,
        }

    def _support_bundle_view() -> dict:
        payload = support_bundle(consented=False, ttl_seconds=0.0, now=0.0)
        return {key: value for key, value in payload.items() if key != "expired"}

    @app.get("/api/support/bundle")
    def get_support_bundle() -> dict:
        return _support_bundle_view()

    @app.post("/api/support/bundle")
    def post_support_bundle(payload: dict | None = None) -> dict:
        del payload
        return _support_bundle_view()

    @app.get("/api/geometry/contact")
    def get_geometry_contact() -> dict:
        return ground_contact_point((0.0, 0.0, 10.0, 20.0))

    @app.post("/api/geometry/contact")
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

    @app.get("/api/geometry/legacy")
    def get_geometry_legacy() -> dict:
        return _legacy_geometry()

    @app.post("/api/geometry/legacy")
    def post_geometry_legacy(payload: dict | None = None) -> dict:
        body = payload or {}
        return _legacy_geometry(list(body.get("points") or []))

    @app.get("/api/geometry/landmarks")
    def get_geometry_landmarks() -> dict:
        return evaluate_landmarks(_legacy_geometry_profile(), max_p95_m=3.0)

    @app.post("/api/geometry/landmarks")
    def post_geometry_landmarks(payload: dict | None = None) -> dict:
        del payload
        return evaluate_landmarks(_legacy_geometry_profile(), max_p95_m=3.0)

    @app.post("/api/geometry/zoom-cut")
    def post_geometry_zoom_cut(payload: dict | None = None) -> dict:
        del payload
        identity = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        shifted = [[1.4, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        previous = CalibrationProfile(calibrationId="prev", cameraModel="planar_homography", homography=identity)
        current = CalibrationProfile(calibrationId="curr", cameraModel="planar_homography", homography=shifted)
        return {"changed": detect_zoom_or_cut(previous, current)}

    @app.get("/api/metrics/network-failure")
    def get_network_failure() -> dict:
        return network_failure_preserves_unknown(metric_value=None, generated_number=0.0)

    @app.post("/api/metrics/network-failure")
    def post_network_failure(payload: dict | None = None) -> dict:
        del payload
        return network_failure_preserves_unknown(metric_value=None, generated_number=0.0)

    @app.get("/api/reports/held-out")
    def get_held_out_questions() -> dict:
        return {"questions": held_out_questions()}

    @app.get("/api/storage/object")
    def get_object_storage() -> dict:
        return object_storage_adapter(hosted_approved=False)

    @app.get("/api/recovery/disk")
    def get_recovery_disk() -> dict:
        return full_disk()

    @app.get("/api/recovery/restore")
    def get_recovery_restore() -> dict:
        return storage.restore_exercise_run()

    @app.get("/api/preemptible")
    def get_preemptible() -> dict:
        return {"allowed": preemptible_allowed(checkpoints=False, restart_semantics=False)}

    @app.post("/api/assistance/repair")
    def post_json_repair(payload: dict | None = None) -> dict:
        body = payload or {}
        attempts = int(body.get("attempts") or 0)
        return json_repair_chain(attempts=attempts, max_repair=1)

    @app.post("/api/assistance/policy")
    def post_assistance_policy(payload: dict | None = None) -> dict:
        body = payload or {}
        return policy_log(
            route=str(body.get("route") or "template"),
            evidence_hash=str(body.get("evidenceHash") or ""),
            secret=str(body.get("secret") or ""),
        )

    @app.post("/api/experiments/quality-gate")
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

    @app.get("/api/experiments/{experiment}")
    def get_experiment(experiment: str) -> dict:
        return experiment_receipt(experiment, hardware_verified=False, bottleneck_documented=False).model_dump(mode="json")

    @app.post("/api/experiments/{experiment}")
    def post_experiment(experiment: str, payload: dict | None = None) -> dict:
        del payload
        return experiment_receipt(experiment, hardware_verified=False, bottleneck_documented=False).model_dump(mode="json")

    @app.get("/api/timing/stages")
    def get_stage_timing() -> dict:
        return stage_timing(
            decode=1.0,
            preprocess=1.0,
            transfer=1.0,
            inference=1.0,
            association=1.0,
            recovery=1.0,
            serialisation=1.0,
            wall_time=3.0,
            overlapped=True,
        ).model_dump(mode="json")

    @app.post("/api/identity/promote")
    def post_identity_promote(payload: dict | None = None) -> dict:
        body = payload or {}
        record = IdentityRecord(kind="tracklet", trackId=str(body.get("trackId") or "t-0"))
        return promote_identity(record, target="roster_player", reviewed=False, rosterId=None).model_dump(mode="json")

    @app.get("/api/identity/clusters/{cluster_id}")
    def get_identity_cluster(cluster_id: int) -> dict:
        return cluster_mapping(cluster_id=cluster_id, selected_semantic=None).model_dump(mode="json")

    @app.post("/api/identity/clusters/{cluster_id}")
    def post_identity_cluster(cluster_id: int, payload: dict | None = None) -> dict:
        del payload
        return cluster_mapping(cluster_id=cluster_id, selected_semantic=None).model_dump(mode="json")

    @app.post("/api/pause")
    def post_pause_experiment(payload: dict | None = None) -> dict:
        del payload
        return {"paused": pause_experiment(remaining=1_000_000.0, termination_and_recovery=0.0)}

    @app.post("/api/quota")
    def post_upload_quota(payload: dict | None = None) -> dict:
        body = payload or {}
        return upload_quota(
            byte_size=int(body.get("byteSize") or 0),
            duration_seconds=float(body.get("durationSeconds") or 0),
        )

    @app.post("/api/worker/import")
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

    @app.get("/api/training/pools")
    def get_training_pools() -> dict:
        return {"pools": list(data_pools())}

    @app.post("/api/training/admit")
    def post_training_admit(payload: dict | None = None) -> dict:
        body = payload or {}
        source = str(body.get("sourcePool") or "locked_evaluation")
        destination = str(body.get("destination") or "training")
        return admit_example(
            {"id": str(body.get("id") or ""), "rights": str(body.get("rights") or "")},
            source_pool=source,  # type: ignore[arg-type]
            destination=destination,  # type: ignore[arg-type]
        ).model_dump(mode="json")

    @app.post("/api/research/paths")
    def post_research_paths(payload: dict | None = None) -> dict:
        body = payload or {}
        return {"allowed": may_write_product_paths(list(body.get("paths") or []))}

    @app.get("/api/flags/shadow/{name}")
    def get_shadow_metric(name: str) -> dict:
        return shadow_metric(name)

    @app.get("/api/flags/{name}/enabled")
    def get_feature_enabled(name: str) -> dict:
        return {"name": name, "enabled": feature_enabled(name, env={})}

    @app.post("/api/flags/{name}/enabled")
    def post_feature_enabled(name: str, payload: dict | None = None) -> dict:
        del payload
        return {"name": name, "enabled": feature_enabled(name, env={})}

    @app.get("/api/quantities/display")
    def get_legacy_display() -> dict:
        return transform_legacy_display(x=0.0, y=0.0, from_display=True)

    @app.post("/api/detector")
    def post_detector(payload: dict | None = None) -> dict:
        body = payload or {}
        return DetectorAdapter().detect(
            {"colourOrder": str(body.get("colourOrder") or "bgr")},
            requested_backend=str(body.get("requestedBackend") or "cuda"),
            video_engine_capability=False,
        )

    @app.post("/api/perception/tiles")
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

    @app.post("/api/sharing")
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

    @app.post("/api/media/colour")
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

    @app.post("/api/decode/wrap")
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

    @app.post("/api/decode/fallback")
    def post_decode_fallback(payload: dict | None = None) -> dict:
        del payload
        return {"selected": cpu_fallback("cuda", {"opencv", "fixture"}), "availableIncludesCuda": False}

    @app.post("/api/perception/preprocess")
    def post_perception_preprocess(payload: dict | None = None) -> dict:
        body = payload or {}
        result = PreprocessorAdapter().transform(
            pixels=_as_bytes(body.get("pixels") or [10, 200, 30]),
            width=int(body.get("width") or 1),
            height=int(body.get("height") or 1),
            colour_order=str(body.get("colourOrder") or "rgb"),
        )
        result.pop("pixels", None)
        return result

    @app.post("/api/perception/score")
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

    @app.post("/api/perception/stratum")
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

    @app.post("/api/perception/ball-states")
    def post_perception_ball_states(payload: dict | None = None) -> dict:
        body = payload or {}
        return separate_ball_states(list(body.get("rows") or []))

    @app.post("/api/identity/preview")
    def post_identity_preview(payload: dict | None = None) -> dict:
        body = payload or {}
        return preview_identity_change(
            kind=str(body.get("kind") or "track_split"),
            track_id=body.get("trackId"),
            at_frame=body.get("atFrame"),
            interval_start=body.get("intervalStart"),
            interval_end=body.get("intervalEnd"),
        )

    @app.post("/api/tracker")
    def post_tracker_associate(payload: dict | None = None) -> dict:
        body = payload or {}
        detections = [_as_detection(item) for item in list(body.get("detections") or [])]
        tracks = TrackerAdapter().associate(
            detections,
            cut_detected=bool(body.get("cutDetected")),
            broadcast_replay=bool(body.get("broadcastReplay")),
        )
        return {"tracks": tracks, "silentlyReconnected": False}

    @app.post("/api/events/propose")
    def post_event_propose(payload: dict | None = None) -> dict:
        body = payload or {}
        event = propose_event(
            family=str(body.get("family") or "pass"),
            release=body.get("release"),
            receipt=body.get("receipt"),
        )
        return event.model_dump(mode="json")

    @app.post("/api/events/score")
    def post_event_score(payload: dict | None = None) -> dict:
        body = payload or {}
        receipt = score_events(
            predictions=list(body.get("predictions") or []),
            labels=list(body.get("labels") or []),
            labels_independent=False,
        )
        return receipt.model_dump(mode="json")

    @app.post("/api/cache/recompute")
    def post_cache_recompute(payload: dict | None = None) -> dict:
        del payload
        return recompute_plan(previous_identity="previous", current_identity="current", change="perception")

    @app.post("/api/training/ledger")
    def post_training_ledger(payload: dict | None = None) -> dict:
        del payload
        ledger = experiment_ledger()
        ledger.append({"run": "exp-1", "config": "baseline"})
        return {"entries": ledger.entries, "promoted": False, "independentGroundTruth": False}

    @app.post("/api/identity/repair")
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

    @app.post("/api/decode/crop")
    def post_decode_crop(payload: dict | None = None) -> dict:
        body = payload or {}
        return apply_crop_and_rotation(
            int(body.get("width") or 1920),
            int(body.get("height") or 1080),
            crop=None,
            rotation=0,
            colour_order="bgr",
        )

    @app.post("/api/decode/cuts")
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

    @app.post("/api/decode/grid")
    def post_decode_grid(payload: dict | None = None) -> dict:
        body = payload or {}
        return align_clip_start_to_grid(
            clip_start_source_frame=int(body.get("clipStartSourceFrame") or 0),
            evaluation_step=int(body.get("evaluationStep") or 1),
        )

    @app.post("/api/decode/pixels")
    def post_decode_pixels(payload: dict | None = None) -> dict:
        del payload
        payload_bytes = b"\x00\x00\x00"
        base = DecodedFrame(0, 0, 0.0, 1, 1, "bgr", 0, payload_bytes, "fixture")
        frame = DecodedFrame(0, 0, 0.0, 1, 1, "bgr", 0, payload_bytes, "fixture", buffer=wrap_decoded_frame(base, device="cpu"))
        pixels = pixels_from_decoded_frame(frame)
        return {"shape": list(pixels.shape), "gpuPromoted": False, "device": "cpu"}

    @app.post("/api/costs/deployment")
    def post_deployment_choice(payload: dict | None = None) -> dict:
        del payload
        return deployment_choice(privacy_required=True, irregular_usage=False, suitable_local_hardware=True)

    @app.get("/api/metrics/round-trip")
    def get_metric_round_trip() -> dict:
        restored = round_trip_unknown(
            unknown_metric("possession_pct", definition_version=DEFINITION_VERSION, reason_codes=["ZERO_DENOMINATOR"])
        )
        dumped = restored.model_dump(mode="json")
        dumped["publishedValue"] = restored.published_value()
        return dumped

    @app.post("/api/metrics/spec")
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

    @app.post("/api/access/object")
    def post_authorize_object(payload: dict | None = None) -> dict:
        body = payload or {}
        return authorize_object(
            object_id=str(body.get("objectId") or ""),
            session_tenant="loopback",
            client_tenant=body.get("clientTenant"),
            object_tenant=body.get("objectTenant"),
        )

    @app.post("/api/decode/sample")
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

    @app.post("/api/decode/pts")
    def post_decode_pts(payload: dict | None = None) -> dict:
        body = payload or {}
        return {
            "seconds": pts_to_seconds(
                int(body.get("pts") or 0),
                int(body.get("timeBaseNum") or 1),
                int(body.get("timeBaseDen") or 1),
            )
        }

    @app.post("/api/decode/proxy-pts")
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

    @app.post("/api/decode/interval")
    def post_decode_interval(payload: dict | None = None) -> dict:
        body = payload or {}
        start, end = resolve_declared_interval(
            str(body.get("kind") or "source"),
            float(body.get("startSeconds") or 0.0),
            float(body.get("endSeconds") or 0.0),
            list(body.get("mapping") or []),
        )
        return {"interval": [start, end]}

    @app.get("/api/rates/four")
    def get_four_rates() -> dict:
        return _four_rates_view()

    @app.post("/api/rates/four")
    def post_four_rates(payload: dict | None = None) -> dict:
        del payload
        return _four_rates_view()

    @app.post("/api/ownership/hysteresis")
    def post_ownership_hysteresis(payload: dict | None = None) -> dict:
        del payload
        hyst = OwnershipHysteresis(min_persistence=3)
        return {"owner": hyst.observe("my_team"), "minPersistence": 3}

    @app.post("/api/metrics/possession-states")
    def post_possession_states(payload: dict | None = None) -> dict:
        body = payload or {}
        summary = possession_from_states(list(body.get("states") or []), float(body.get("requestedSeconds") or 0.0))
        dumped = summary.model_dump(mode="json")
        dumped["publishedValue"] = summary.published_value()
        return dumped

    @app.post("/api/reports/template")
    def post_template_report(payload: dict | None = None) -> dict:
        del payload
        return template_report([], [])

    @app.get("/api/receipts/promotion")
    def get_promotion_receipt() -> dict:
        return _unpromoted_receipt()

    @app.post("/api/receipts/promotion")
    def post_promotion_receipt(payload: dict | None = None) -> dict:
        del payload
        return _unpromoted_receipt()

    @app.post("/api/ownership/invalidate")
    def post_ownership_invalidate(payload: dict | None = None) -> dict:
        del payload
        return {"change": "track_edit", "invalidates": ownership_invalidation()}

    @app.get("/api/quantities/scores")
    def get_split_scores() -> dict:
        return split_scores(detector_score=None, calibrated_probability=None, interval=None)

    @app.post("/api/quantities/scores")
    def post_split_scores(payload: dict | None = None) -> dict:
        body = payload or {}
        interval = body.get("interval")
        return split_scores(
            detector_score=body.get("detectorScore"),
            calibrated_probability=body.get("calibratedProbability"),
            interval=tuple(interval) if interval else None,
        )

    @app.post("/api/worker/environment")
    def post_worker_environment(payload: dict | None = None) -> dict:
        del payload
        return worker_environment(_production_job_request(), host_secret="")

    @app.post("/api/cleanup/complete")
    def post_cleanup_complete(payload: dict | None = None) -> dict:
        del payload
        return {"complete": cleanup_failure_is_complete("failed"), "cleanupResult": "failed"}

    @app.post("/api/upload/interrupt")
    def post_upload_interrupt(payload: dict | None = None) -> dict:
        del payload
        return storage.interrupted_upload_run()

    @app.get("/api/access/signed")
    def get_signed_object_access() -> dict:
        return signed_scoped_object_access(token=None, object_id="", token_object_id=None)

    @app.post("/api/access/signed")
    def post_signed_object_access(payload: dict | None = None) -> dict:
        del payload
        return signed_scoped_object_access(token=None, object_id="", token_object_id=None)

    @app.post("/api/training/cycle")
    def post_training_cycle(payload: dict | None = None) -> dict:
        body = payload or {}
        return experiment_cycle(
            str(body.get("stage") or "diagnose"),
            measurable_failure=False,
            budget_remaining=0.0,
            development_benefit=False,
            gate_regressed=True,
        )

    @app.post("/api/training/promote")
    def post_training_promote(payload: dict | None = None) -> dict:
        del payload
        return promote_candidate(independent_accepted=False, rollback_artifact=True)

    @app.post("/api/training/pseudo")
    def post_training_pseudo(payload: dict | None = None) -> dict:
        body = payload or {}
        return pseudo_label(suggestion=str(body.get("suggestion") or ""), human_change=None, approved=False)

    @app.get("/api/training/sampling")
    def get_training_sampling() -> dict:
        return sampling_policy()

    @app.post("/api/search")
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
        return storage.query_match_events(match_id, str(body.get("query") or ""))

    @app.post("/api/playlists/export-interval")
    def export_playlist_interval(payload: dict | None = None) -> dict:
        body = payload or {}
        try:
            return playlist_export_interval(body, float(body.get("sourceFps") or 25.0))
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/matches")
    def list_matches() -> list[dict]:
        return [match.model_dump(mode="json") for match in storage.list_matches()]

    @app.get("/api/matches/{match_id}")
    def get_match(match: MatchRecord = Depends(require_match)) -> dict:
        return match.model_dump(mode="json")

    @app.post("/api/matches/{match_id}/jobs", status_code=202)
    def post_match_job(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        request_id = str(body.get("requestId") or uuid.uuid4().hex)
        budget = float(body.get("budget") or 0.0)
        try:
            job, created = storage.ensure_job(match.id, request_id, created_status="queued")
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
    ) -> dict:
        try:
            page = storage.load_frames_page(match.id, after_frame=afterFrame, cursor=cursor, limit=limit)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc
        response = MatchFramesResponse(
            matchId=match.id,
            frames=page["frames"],
            nextCursor=page["nextCursor"],
            frameCount=page["frameCount"],
            intervalEndpoint=page["intervalEndpoint"],
        )
        return response.model_dump(mode="json")

    @app.get("/api/matches/{match_id}/evidence")
    def get_match_evidence(
        match: MatchRecord = Depends(require_match),
        intervalStart: float | None = None,
        intervalEnd: float | None = None,
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict:
        try:
            return storage.load_evidence_page(
                match.id,
                interval_start=intervalStart,
                interval_end=intervalEnd,
                cursor=cursor,
                limit=limit,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Evidence not ready") from exc

    @app.get("/api/matches/{match_id}/analytics")
    def get_analytics(match: MatchRecord = Depends(require_match)) -> dict:
        try:
            summary, assignments, formation_timeline, shots = storage.load_analytics(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc
        response = MatchAnalyticsResponse(
            matchId=match.id,
            summary=summary,
            ballAssignments=assignments,
            formationTimeline=formation_timeline,
            shots=shots,
        )
        return response.model_dump(mode="json")

    @app.post("/api/matches/{match_id}/corrections")
    def post_match_correction(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        try:
            saved = storage.submit_correction(
                match.id,
                kind=str(body.get("kind") or ""),
                payload=dict(body.get("payload") or {}),
                author=str(body.get("author") or "analyst"),
                expected_version=body.get("expectedVersion"),
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
    def undo_match_correction(correction_id: str, match: MatchRecord = Depends(require_match)) -> dict:
        try:
            saved = storage.undo_correction(match.id, correction_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Correction not found") from exc
        return correction_api_payload(saved)

    @app.get("/api/matches/{match_id}/corrections")
    def list_match_corrections(match: MatchRecord = Depends(require_match), state: str | None = None) -> dict:
        return {"items": storage.list_corrections(match.id, state=state)}

    @app.post("/api/matches/{match_id}/queries")
    def post_match_query(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        return storage.query_match_events(match.id, str(body.get("query") or ""))

    @app.post("/api/matches/{match_id}/reports")
    def post_match_report(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        claimed = body.get("claimedEvidenceIds")
        try:
            return storage.assemble_match_report(
                match.id,
                claimed_evidence_ids=list(claimed) if claimed is not None else None,
                narrative=body.get("narrative"),
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc

    @app.get("/api/matches/{match_id}/players")
    def get_match_players(match: MatchRecord = Depends(require_match)) -> dict:
        try:
            return storage.player_observations_for_match(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc

    @app.post("/api/matches/{match_id}/players")
    def post_match_players(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return get_match_players(match)

    @app.get("/api/matches/{match_id}/ownership")
    def get_match_ownership(match: MatchRecord = Depends(require_match)) -> dict:
        try:
            return storage.classify_match_ownership(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc

    @app.post("/api/matches/{match_id}/ownership")
    def post_match_ownership(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return get_match_ownership(match)

    @app.get("/api/matches/{match_id}/package")
    def get_match_package(match: MatchRecord = Depends(require_match)) -> dict:
        try:
            return storage.assemble_stored_match_package(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc

    @app.post("/api/matches/{match_id}/package")
    def post_match_package(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return get_match_package(match)

    @app.get("/api/matches/{match_id}/incidents/geometry")
    def get_match_incident_geometry(match: MatchRecord = Depends(require_match)) -> dict:
        try:
            return storage.incident_geometry_for_match(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc

    @app.post("/api/matches/{match_id}/incidents/geometry")
    def post_match_incident_geometry(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return get_match_incident_geometry(match)

    @app.get("/api/matches/{match_id}/setup")
    def match_setup(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.assess_stored_match_setup(match.id)

    @app.get("/api/matches/{match_id}/rates")
    def match_rates(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.four_rates_for_match(match.id)

    @app.get("/api/matches/{match_id}/metrics")
    def get_match_metrics(match: MatchRecord = Depends(require_match)) -> dict:
        try:
            return storage.match_metrics_for_match(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc

    @app.post("/api/matches/{match_id}/metrics")
    def post_match_metrics(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return get_match_metrics(match)

    @app.get("/api/matches/{match_id}/metrics/inspect/{metric}")
    def inspect_stored_metric(metric: str, match: MatchRecord = Depends(require_match)) -> dict:
        try:
            return storage.inspect_match_metric(match.id, metric)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc

    @app.get("/api/matches/{match_id}/incidents/package")
    def get_match_incident_package(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.incident_package_for_match(match.id)

    @app.post("/api/matches/{match_id}/incidents/package")
    def post_match_incident_package(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return get_match_incident_package(match)

    @app.get("/api/matches/{match_id}/clock")
    def get_match_clock(match: MatchRecord = Depends(require_match)) -> dict:
        try:
            return storage.clock_for_match(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc

    @app.get("/api/matches/{match_id}/incidents/review")
    def get_match_incident_review(match: MatchRecord = Depends(require_match)) -> dict:
        try:
            return storage.incident_review_for_match(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc

    @app.post("/api/matches/{match_id}/incidents/review")
    def post_match_incident_review(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return get_match_incident_review(match)

    @app.get("/api/matches/{match_id}/privacy")
    def get_match_privacy(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.dpia_for_match(match.id)

    @app.get("/api/matches/{match_id}/setup/preview")
    def get_match_setup_preview(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.preview_landmark_for_match(match.id)

    @app.post("/api/matches/{match_id}/recompute")
    def post_match_recompute(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        return storage.recompute_for_match(match.id, str(body.get("change") or "report"))

    @app.get("/api/matches/{match_id}/promotion")
    def get_match_promotion(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.promotion_receipt_for_match(match.id)

    @app.post("/api/matches/{match_id}/assistance/fallback")
    def post_match_assistance_fallback(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        try:
            return storage.assistance_fallback_for_match(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc

    @app.get("/api/matches/{match_id}/quality")
    def get_match_quality(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.quality_timeline_for_match(match.id)

    @app.get("/api/matches/{match_id}/identity")
    def get_match_identity(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.identity_for_match(match.id)

    @app.get("/api/matches/{match_id}/history")
    def get_match_history(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.history_for_match(match.id)

    @app.get("/api/matches/{match_id}/cache")
    def get_match_cache(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.cache_identity_for_match(match.id)

    @app.post("/api/matches/{match_id}/cache")
    def post_match_cache(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.cache_identity_for_match(match.id)

    @app.get("/api/matches/{match_id}/records/migrate")
    def get_match_legacy_migrate(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.migrate_legacy_for_match(match.id)

    @app.post("/api/matches/{match_id}/records/migrate")
    def post_match_legacy_migrate(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
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
        del payload
        return storage.calibration_for_match(match.id)

    @app.get("/api/matches/{match_id}/formation")
    def get_match_formation(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.formation_for_match(match.id)

    @app.post("/api/matches/{match_id}/formation")
    def post_match_formation(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.formation_for_match(match.id)

    @app.get("/api/matches/{match_id}/events/partition")
    def get_match_event_partition(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.partition_events_for_match(match.id)

    @app.post("/api/matches/{match_id}/events/partition")
    def post_match_event_partition(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.partition_events_for_match(match.id)

    @app.get("/api/matches/{match_id}/reports/provenance")
    def get_match_report_provenance(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.provenance_for_match(match.id)

    @app.post("/api/matches/{match_id}/reports/provenance")
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

    @app.get("/api/matches/{match_id}/reports/coverage")
    def get_match_report_coverage(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.coverage_for_match(match.id)

    @app.get("/api/matches/{match_id}/shots/quality")
    def get_match_shot_quality(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.shot_quality_for_match(match.id)

    @app.post("/api/matches/{match_id}/shots/quality")
    def post_match_shot_quality(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.shot_quality_for_match(match.id)

    @app.get("/api/matches/{match_id}/media/proxy")
    def get_match_proxy(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.proxy_assets_for_match(match.id)

    @app.get("/api/matches/{match_id}/edits")
    def get_match_edits(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.edit_list_for_match(match.id)

    @app.post("/api/matches/{match_id}/edits/render")
    def post_match_edit_render(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        return storage.render_edit_for_match(
            match.id,
            start=float(body.get("start") or 0.0),
            end=float(body.get("end") or 0.0),
        )

    @app.post("/api/matches/{match_id}/artifacts/alongside")
    def post_match_write_alongside(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.write_alongside_for_match(match.id)

    @app.get("/api/matches/{match_id}/tracklets")
    def get_match_tracklets(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.tracklets_for_match(match.id)

    @app.post("/api/matches/{match_id}/tracklets")
    def post_match_tracklets(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.tracklets_for_match(match.id)

    @app.get("/api/matches/{match_id}/geometry/distance")
    def get_match_derived_distance(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.derived_distance_for_match(match.id)

    @app.get("/api/matches/{match_id}/shots/features")
    def get_match_shot_features(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.shot_features_for_match(match.id)

    @app.post("/api/matches/{match_id}/shots/features")
    def post_match_shot_features(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
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
                claimed_evidence_ids=list(claimed) if claimed is not None else None,
                narrative=body.get("narrative"),
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc

    @app.get("/api/matches/{match_id}/events")
    def get_events(match: MatchRecord = Depends(require_match)) -> dict:
        try:
            events = storage.load_events(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Events not ready") from exc
        response = MatchEventsResponse(matchId=match.id, events=events)
        return response.model_dump(mode="json")

    @app.get("/api/matches/{match_id}/export/frames.csv")
    def export_frames_csv(match: MatchRecord = Depends(require_match)) -> Response:
        try:
            frames = storage.load_frames(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc
        csv_payload = render_csv(flatten_frames_for_csv(frames), FRAME_CSV_FIELDS)
        headers = {"Content-Disposition": f'attachment; filename="{match.id}-frames.csv"'}
        return Response(content=csv_payload, media_type="text/csv", headers=headers)

    @app.get("/api/matches/{match_id}/export/events.csv")
    def export_events_csv(match: MatchRecord = Depends(require_match)) -> Response:
        try:
            events = storage.load_events(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Events not ready") from exc
        csv_payload = render_csv(flatten_events_for_csv(events), EVENT_CSV_FIELDS)
        headers = {"Content-Disposition": f'attachment; filename="{match.id}-events.csv"'}
        return Response(content=csv_payload, media_type="text/csv", headers=headers)

    @app.get("/api/matches/{match_id}/export/metrics.csv")
    def export_metrics_csv(match: MatchRecord = Depends(require_match)) -> Response:
        try:
            summary, _assignments, _formation, _shots = storage.load_analytics(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc
        csv_payload = render_csv(flatten_metrics_for_csv(summary.metricAvailability), METRIC_CSV_FIELDS)
        headers = {"Content-Disposition": f'attachment; filename="{match.id}-metrics.csv"'}
        return Response(content=csv_payload, media_type="text/csv", headers=headers)

    @app.get("/api/matches/{match_id}/export/match.json")
    def export_match_json(match: MatchRecord = Depends(require_match)) -> dict:
        try:
            return build_match_bundle(storage, match.id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Match artifacts not ready") from exc

    @app.post("/api/matches/{match_id}/analysis/{analysis_type}")
    def analyze_match(analysis_type: str, match: MatchRecord = Depends(require_match), body: dict | None = None) -> dict:
        match_id = match.id
        with storage.config_update_lock:
            try:
                snapshot = storage.get_match(match_id)
                frames = storage.load_frames(match_id)
            except (KeyError, FileNotFoundError) as exc:
                raise HTTPException(status_code=404, detail="Frames not ready") from exc

            body = body or {}
            provider = body.get("provider") or snapshot.config.llmProvider
            current_frame_index = body.get("currentFrameIndex")
            summary = None
            formation_timeline = None
            events = None
            shots = None
            if analysis_type in {"tactical_report", "drills"}:
                try:
                    summary, _, formation_timeline, shots = storage.load_analytics(match_id)
                except FileNotFoundError:
                    summary = None
                    formation_timeline = None
                    shots = None
                try:
                    events = storage.load_events(match_id)
                except FileNotFoundError:
                    events = None
        try:
            result = run_analysis(
                analysis_type,
                frames,
                provider=provider,
                attack_direction=snapshot.config.attackDirection,
                current_frame_index=current_frame_index,
                summary=summary,
                events=events,
                formation_timeline=formation_timeline,
                shots=shots,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        with storage.config_update_lock:
            if storage.get_match(match_id).updatedAt != snapshot.updatedAt:
                raise HTTPException(status_code=409, detail="Match changed during analysis; run it again.")
            if analysis_type in {"tactical_report", "drills"} and isinstance(result, dict):
                storage.save_analysis_artifact(match_id, analysis_type, result)
        return result

    @app.get("/api/matches/{match_id}/report/html")
    def get_match_report_html(match: MatchRecord = Depends(require_match)) -> HTMLResponse:
        try:
            summary, _, formation_timeline, shots = storage.load_analytics(match.id)
            events = storage.load_events(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc

        try:
            tactical_report = storage.load_analysis_artifact(match.id, "tactical_report")
        except FileNotFoundError:
            tactical_report = None

        try:
            drills = storage.load_analysis_artifact(match.id, "drills")
        except FileNotFoundError:
            drills = None

        html = build_match_report_export(
            match=match,
            summary=summary,
            formation_timeline=formation_timeline,
            shots=shots,
            events=events,
            tactical_report=tactical_report,
            drills=drills,
        )
        return HTMLResponse(content=html)

    @app.get("/api/matches/{match_id}/benchmark")
    def get_match_benchmark(match: MatchRecord = Depends(require_match), includeSelectedClusterProbe: bool = False) -> dict:
        try:
            summary = summarize_match_benchmark(storage, match.id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Benchmark not ready") from exc

        if not includeSelectedClusterProbe:
            return summary.model_dump(mode="json")

        response: dict[str, object] = {"saved": summary.model_dump(mode="json")}
        response.update(build_selected_cluster_payload(storage, match.id))
        return response

    @app.patch("/api/matches/{match_id}/config")
    def update_match_config(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        match_id = match.id
        payload = payload or {}
        with storage.config_update_lock:
            try:
                match = storage.get_match(match_id)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail="Match not found") from exc

            merged = match.config.model_dump()
            merged.update(payload)
            try:
                config_model = MatchConfig.model_validate(merged, strict=True)
            except ValidationError as exc:
                raise HTTPException(status_code=422, detail=exc.errors(include_context=False, include_input=False)) from exc

            selected_cluster = config_model.myTeamCluster
            available_cluster_ids = {cluster.clusterId for cluster in match.teamClusters}
            if selected_cluster is not None and available_cluster_ids and selected_cluster not in available_cluster_ids:
                raise HTTPException(status_code=400, detail="myTeamCluster must match one of the detected team clusters.")

            needs_reprocessing = (
                config_model.attackDirection != match.config.attackDirection
                or (match.inputMode == "video" and config_model.myTeamCluster != match.config.myTeamCluster)
            )
            if needs_reprocessing:
                if match.status == "processing" or storage.has_active_job(match_id):
                    raise HTTPException(status_code=409, detail="Match processing must finish before changing analytical configuration.")
                try:
                    with storage.remote_result_import(match_id):
                        reprocess_video_match(storage, match_id, config=config_model)
                        storage.invalidate_coach_analysis(match_id)
                        storage.update_match_config(match_id, config_model)
                except FileNotFoundError as exc:
                    raise HTTPException(status_code=409, detail="Required match artifacts are not available for reprocessing.") from exc
            else:
                storage.update_match_config(match_id, config_model)

            return storage.get_match(match_id).model_dump(mode="json")

    @app.websocket("/ws/jobs/{job_id}")
    async def job_updates(websocket: WebSocket, job_id: str) -> None:
        await websocket.accept()
        last_payload = None
        try:
            while True:
                try:
                    payload = (await run_in_threadpool(storage.get_job, job_id)).model_dump(mode="json")
                except KeyError:
                    await websocket.send_json({"error": "Job not found"})
                    await websocket.close()
                    return
                if payload != last_payload:
                    await websocket.send_json(payload)
                    last_payload = payload
                if payload["status"] in {"completed", "failed"}:
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
                    matchCount=0, avgPossession=None, avgMyTeamXg=0.0, avgEnemyXg=0.0,
                    avgXgDiff=0.0, avgMyTeamSprints=None, avgEnemySprints=None,
                    mostUsedFormation="-",
                ),
            )
            return empty.model_dump(mode="json")

        summaries = [m["summary"] for m in all_matches]
        n = len(summaries)
        measured_possession = [s["possession"] for s in summaries if s.get("possession") is not None]
        avg_pos = sum(measured_possession) / len(measured_possession) if measured_possession else None
        avg_my_xg = sum(s.get("myTeamXg", 0) for s in summaries) / n
        avg_enemy_xg = sum(s.get("enemyXg", 0) for s in summaries) / n
        avg_xg_diff = avg_my_xg - avg_enemy_xg
        avg_my_sprints = _dashboard_average(summaries, field="myTeamSprints", metric="my_team_sprints")
        avg_enemy_sprints = _dashboard_average(summaries, field="enemySprints", metric="enemy_sprints")

        from collections import Counter
        formations = [s.get("formation", "-") for s in summaries if s.get("formation")]
        most_used = Counter(formations).most_common(1)[0][0] if formations else "-"

        summary = DashboardSummary(
            matchCount=n,
            avgPossession=round(avg_pos, 1) if avg_pos is not None else None,
            avgMyTeamXg=round(avg_my_xg, 2),
            avgEnemyXg=round(avg_enemy_xg, 2),
            avgXgDiff=round(avg_xg_diff, 2),
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
                xgDiffDelta=round(
                    (s_latest.get("myTeamXg", 0) - s_latest.get("enemyXg", 0))
                    - (s_prev.get("myTeamXg", 0) - s_prev.get("enemyXg", 0)),
                    2,
                ),
                myTeamSprintsDelta=(
                    round(s_latest.get("myTeamSprints", 0) - s_prev.get("myTeamSprints", 0), 1)
                    if _dashboard_metric_measured(s_latest, "my_team_sprints")
                    and _dashboard_metric_measured(s_prev, "my_team_sprints")
                    else None
                ),
                enemySprintsDelta=(
                    round(s_latest.get("enemySprints", 0) - s_prev.get("enemySprints", 0), 1)
                    if _dashboard_metric_measured(s_latest, "enemy_sprints")
                    and _dashboard_metric_measured(s_prev, "enemy_sprints")
                    else None
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

    return app


app = create_app()
