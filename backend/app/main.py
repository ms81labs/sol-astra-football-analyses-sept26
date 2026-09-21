from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    Request,
    WebSocket,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.datastructures import Headers
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import (
    ASGIApp,
    Receive,
    Scope,
    Send,
)

from .jobs import JobRunner
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
from .provider_gateway import (
    ProviderBudgetLedger,
    ProviderGateway,
)
from .review_routes import create_review_router
from .artifact_routes import create_artifact_router
from . import insight_routes as _insight_routes
from .insight_routes import create_insight_router
from .settings import (
    ProcessingSettings,
    SettingsError,
    canonicalize_origin,
)
from .schemas import (
    MatchConfig,
    MatchRecord,
)
from .storage import Storage
from .workbench.access import (
    object_access_decision,
    verify_hosted_token,
)
from .workbench.routes import create_workbench_router

# Compatibility export retained for tests/internal callers that historically imported
# this helper from backend.app.main. The implementation now lives with insight routes.
_dashboard_average = _insight_routes._dashboard_average

STORAGE_ROOT_ENV = "GUERILLA_STORAGE_ROOT"
LOGGER = logging.getLogger(__name__)


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
