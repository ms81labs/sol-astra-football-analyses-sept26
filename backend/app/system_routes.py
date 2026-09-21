"""System, policy, and utility API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .storage import Storage
from .workbench.access import access_deletion_procedure
from .workbench.admission import admit_media
from .workbench.contracts import SourceClockIdentity
from .workbench.costs import match_cost
from .workbench.dossier import http_dossier
from .workbench.evidence import inspect_metric, metric_dictionary
from .workbench.flags import feature_flags
from .workbench.retention import PROTECTED, may_delete
from .workbench.review import playlist_export_interval
from .workbench.rights import evaluate_rights
from .workbench.rollback import rollback_release


def create_system_router(storage: Storage) -> APIRouter:
    router = APIRouter()

    @router.get("/api/metrics/dictionary")
    
    @router.get("/api/flags")
    
    @router.get("/api/dossier")
    
    @router.get("/api/capabilities")
    
    @router.post("/api/library/search")
    
    @router.get("/api/metrics/inspect/{metric}")
    
    @router.post("/api/rollback")
    
    @router.post("/api/media/admit")
    
    @router.post("/api/cost/estimate")
    
    @router.post("/api/rights/evaluate")
    
    @router.post("/api/access/deletion")
    
    @router.post("/api/retention/delete")
    
    @router.post("/api/playlists/export-interval")

    return router
