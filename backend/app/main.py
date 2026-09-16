from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
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
from .workbench.routes import create_workbench_router


STORAGE_ROOT_ENV = "GUERILLA_STORAGE_ROOT"
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
    app.include_router(create_workbench_router(storage.storage_root))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.trusted_frontend_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Idempotency-Key"],
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

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        try:
            return storage.get_job(job_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc

    @app.get("/api/matches")
    def list_matches() -> list[dict]:
        return [match.model_dump(mode="json") for match in storage.list_matches()]

    @app.get("/api/matches/{match_id}")
    def get_match(match_id: str) -> dict:
        try:
            return storage.get_match(match_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc

    @app.get("/api/matches/{match_id}/video")
    def get_match_video(match_id: str):
        try:
            match = storage.get_match(match_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc

        if match.inputMode != "video":
            raise HTTPException(status_code=409, detail="Video playback is only available for video-backed matches.")

        video_path = storage.get_match_input_path(match_id)
        if not video_path.exists():
            raise HTTPException(status_code=404, detail="Video file not found.")

        return FileResponse(video_path, media_type="video/mp4", filename=match.originalFilename)

    @app.get("/api/matches/{match_id}/frames")
    def get_frames(
        match_id: str,
        afterFrame: int | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> dict:
        try:
            page = storage.load_frames_page(match_id, after_frame=afterFrame, cursor=cursor, limit=limit)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc
        response = MatchFramesResponse(
            matchId=match_id,
            frames=page["frames"],
            nextCursor=page["nextCursor"],
            frameCount=page["frameCount"],
            intervalEndpoint=page["intervalEndpoint"],
        )
        return response.model_dump(mode="json")

    @app.get("/api/matches/{match_id}/analytics")
    def get_analytics(match_id: str) -> dict:
        try:
            summary, assignments, formation_timeline, shots = storage.load_analytics(match_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc
        response = MatchAnalyticsResponse(
            matchId=match_id,
            summary=summary,
            ballAssignments=assignments,
            formationTimeline=formation_timeline,
            shots=shots,
        )
        return response.model_dump(mode="json")

    @app.get("/api/matches/{match_id}/events")
    def get_events(match_id: str) -> dict:
        try:
            events = storage.load_events(match_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Events not ready") from exc
        response = MatchEventsResponse(matchId=match_id, events=events)
        return response.model_dump(mode="json")

    @app.get("/api/matches/{match_id}/export/frames.csv")
    def export_frames_csv(match_id: str) -> Response:
        try:
            frames = storage.load_frames(match_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc
        csv_payload = render_csv(flatten_frames_for_csv(frames), FRAME_CSV_FIELDS)
        headers = {"Content-Disposition": f'attachment; filename="{match_id}-frames.csv"'}
        return Response(content=csv_payload, media_type="text/csv", headers=headers)

    @app.get("/api/matches/{match_id}/export/events.csv")
    def export_events_csv(match_id: str) -> Response:
        try:
            events = storage.load_events(match_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Events not ready") from exc
        csv_payload = render_csv(flatten_events_for_csv(events), EVENT_CSV_FIELDS)
        headers = {"Content-Disposition": f'attachment; filename="{match_id}-events.csv"'}
        return Response(content=csv_payload, media_type="text/csv", headers=headers)

    @app.get("/api/matches/{match_id}/export/metrics.csv")
    def export_metrics_csv(match_id: str) -> Response:
        try:
            summary, _assignments, _formation, _shots = storage.load_analytics(match_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc
        csv_payload = render_csv(flatten_metrics_for_csv(summary.metricAvailability), METRIC_CSV_FIELDS)
        headers = {"Content-Disposition": f'attachment; filename="{match_id}-metrics.csv"'}
        return Response(content=csv_payload, media_type="text/csv", headers=headers)

    @app.get("/api/matches/{match_id}/export/match.json")
    def export_match_json(match_id: str) -> dict:
        try:
            return build_match_bundle(storage, match_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Match artifacts not ready") from exc

    @app.post("/api/matches/{match_id}/analysis/{analysis_type}")
    def analyze_match(match_id: str, analysis_type: str, body: dict | None = None) -> dict:
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
    def get_match_report_html(match_id: str) -> HTMLResponse:
        try:
            match = storage.get_match(match_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc

        try:
            summary, _, formation_timeline, shots = storage.load_analytics(match_id)
            events = storage.load_events(match_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc

        try:
            tactical_report = storage.load_analysis_artifact(match_id, "tactical_report")
        except FileNotFoundError:
            tactical_report = None

        try:
            drills = storage.load_analysis_artifact(match_id, "drills")
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
    def get_match_benchmark(match_id: str, includeSelectedClusterProbe: bool = False) -> dict:
        try:
            storage.get_match(match_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc

        try:
            summary = summarize_match_benchmark(storage, match_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Benchmark not ready") from exc

        if not includeSelectedClusterProbe:
            return summary.model_dump(mode="json")

        response: dict[str, object] = {"saved": summary.model_dump(mode="json")}
        response.update(build_selected_cluster_payload(storage, match_id))
        return response

    @app.patch("/api/matches/{match_id}/config")
    def update_match_config(match_id: str, payload: dict) -> dict:
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
    def list_annotations(match_id: str) -> dict:
        """List all annotations for a match."""
        try:
            annotations = storage.list_annotations(match_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc
        return {"matchId": match_id, "annotations": [a.model_dump(mode="json") for a in annotations]}

    @app.post("/api/matches/{match_id}/annotations", status_code=201)
    def create_annotation(match_id: str, request: CreateAnnotationRequest) -> dict:
        """Create a new annotation on a match."""
        try:
            record = storage.create_annotation(match_id, request)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc
        return record.model_dump(mode="json")

    @app.delete("/api/matches/{match_id}/annotations/{annotation_id}", status_code=204)
    def delete_annotation(match_id: str, annotation_id: str) -> None:
        """Delete an annotation."""
        try:
            storage.delete_annotation(match_id, annotation_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc

    @app.get("/api/matches/{match_id}/issues")
    def list_issues(match_id: str) -> dict:
        """List all issues for a match."""
        try:
            issues = storage.list_issues(match_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc
        return {"matchId": match_id, "issues": [i.model_dump(mode="json") for i in issues]}

    @app.post("/api/matches/{match_id}/issues", status_code=201)
    def create_issue(match_id: str, request: CreateIssueRequest) -> dict:
        """Create a new issue on a match."""
        try:
            record = storage.create_issue(match_id, request)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc
        return record.model_dump(mode="json")

    @app.delete("/api/matches/{match_id}/issues/{issue_id}", status_code=204)
    def delete_issue(match_id: str, issue_id: str) -> None:
        """Delete an issue."""
        try:
            storage.delete_issue(match_id, issue_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc

    @app.get("/api/matches/{match_id}/trust-crops")
    def get_trust_crops(match_id: str, limit: int = 20) -> dict:
        """Compute heuristic-based trust crop queue for a match.

        Frames are scored by uncertainty: ball teleport distance,
        track ID switch frequency, team flip rate, possession gaps.
        """
        try:
            frames = storage.load_frames(match_id)
            summary, assignments, _, _ = storage.load_analytics(match_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames or analytics not ready") from exc

        frames_dicts = [f.model_dump() for f in frames]
        assignments_dicts = [a.model_dump() for a in assignments]
        crops = compute_trust_crops(frames_dicts, assignments_dicts, max_crops=limit)
        response = TrustCropsResponse(
            matchId=match_id,
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
    def get_match_themes(match_id: str) -> dict:
        """Get detected tactical themes for a specific match.
        
        Returns:
            Match with detected tactical themes and strength scores
        """
        try:
            summary, _, _, _ = storage.load_analytics(match_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc
        
        theme_data = detect_themes_for_match(summary.model_dump(mode="json"))
        
        return {
            "matchId": match_id,
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
