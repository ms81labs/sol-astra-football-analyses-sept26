"""Core match read, media, analytics, and correction routes."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import ValidationError

from .schemas import MatchAnalyticsResponse, MatchFramesResponse, MatchRecord
from .settings import ProcessingSettings
from .storage import Storage
from .workbench.review import correction_api_payload


def create_match_runtime_router(
    storage: Storage,
    settings: ProcessingSettings,
    require_match: Callable[..., MatchRecord],
    snapshot_response: Callable[..., dict],
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/matches")
    
    @router.get("/api/matches/{match_id}")
    
    @router.get("/api/matches/{match_id}/video")
    
    @router.get("/api/matches/{match_id}/frames")
    
    @router.get("/api/matches/{match_id}/evidence")
    
    @router.get("/api/matches/{match_id}/analytics")
    
    @router.post("/api/matches/{match_id}/corrections")
    
    @router.post("/api/matches/{match_id}/corrections/{correction_id}/recover")
    
    @router.post("/api/matches/{match_id}/corrections/{correction_id}/undo")
    
    @router.get("/api/matches/{match_id}/corrections")

    return router
