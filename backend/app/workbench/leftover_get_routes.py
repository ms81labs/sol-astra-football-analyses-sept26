"""Leftover contract GET handlers, isolated from the production /api surface."""

from __future__ import annotations

from .leftover_report_routes import register_external_report_routes, register_video_report_routes
from .leftover_info_routes import register_governance_get_routes, register_runtime_get_routes, register_diagnostic_get_routes



from fastapi import APIRouter, FastAPI

from ..storage import Storage
from .leftover_http import leftover_http_enabled


def create_leftover_get_router(storage: Storage) -> APIRouter:
    json_router, _html_router = create_leftover_get_routers(storage)
    return json_router


def create_leftover_get_routers(storage: Storage) -> tuple[APIRouter, APIRouter]:
    router = APIRouter()
    html_router = APIRouter()
    register_external_report_routes(router, html_router, storage)
    register_video_report_routes(router, html_router, storage)
    register_governance_get_routes(router, storage)
    register_runtime_get_routes(router, storage)
    register_diagnostic_get_routes(router, storage)
    return router, html_router


def attach_leftover_get_routes(app: FastAPI, storage: Storage) -> None:
    leftover, html = create_leftover_get_routers(storage)
    app.include_router(leftover, prefix="/api/workbench/dev")
    if leftover_http_enabled():
        app.include_router(leftover, prefix="/api")
        app.include_router(html, prefix="")
