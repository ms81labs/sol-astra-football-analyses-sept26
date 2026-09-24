"""Leftover contract POST handlers, isolated from the production /api surface."""

from __future__ import annotations

from .leftover_analysis_routes import register_governance_post_routes, register_perception_post_routes
from .leftover_media_routes import register_media_post_routes
from .leftover_match_routes import register_evidence_post_routes, register_match_post_routes



from fastapi import APIRouter
from fastapi import FastAPI

from ..storage import Storage
from .leftover_http import leftover_http_enabled



def create_leftover_post_router(storage: Storage) -> APIRouter:
    router = APIRouter()
    register_governance_post_routes(router, storage)
    register_perception_post_routes(router, storage)
    register_media_post_routes(router, storage)
    register_evidence_post_routes(router, storage)
    register_match_post_routes(router, storage)
    return router


def attach_leftover_post_routes(app: FastAPI, storage: Storage) -> None:
    leftover = create_leftover_post_router(storage)
    app.include_router(leftover, prefix="/api/workbench/dev")
    if leftover_http_enabled():
        app.include_router(leftover, prefix="/api")
