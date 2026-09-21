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
    def get_metric_dictionary() -> dict:
        return {"metrics": metric_dictionary()}
    
    
    @router.get("/api/flags")
    def get_feature_flags() -> dict:
        return feature_flags()
    
    
    @router.get("/api/dossier")
    def get_dossier() -> dict:
        payload = http_dossier()
        return {key: payload[key] for key in ("baseline", "release", "evaluation", "gpu", "native")}
    
    
    @router.get("/api/capabilities")
    def get_capabilities() -> dict:
        return {"capabilities": http_dossier()["capabilities"]}
    
    
    @router.post("/api/library/search")
    def post_library_search(payload: dict | None = None) -> dict:
        body = payload or {}
        return storage.search_stored_library(str(body.get("query") or ""))
    
    
    @router.get("/api/metrics/inspect/{metric}")
    def get_metric_inspect(metric: str) -> dict:
        return inspect_metric(metric)
    
    
    @router.post("/api/rollback")
    def post_rollback(payload: dict | None = None) -> dict:
        body = payload or {}
        return rollback_release(
            flag_name=str(body.get("flagName") or "unspecified"),
            affected_outputs=list(body.get("affectedOutputs") or []),
        )
    
    
    @router.post("/api/media/admit")
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
    
    
    @router.post("/api/cost/estimate")
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
    
    
    @router.post("/api/rights/evaluate")
    def post_rights_evaluate(payload: dict | None = None) -> dict:
        body = payload or {}
        return evaluate_rights(
            {
                "asset": str(body.get("asset") or "match_recording"),
                "commercialPermission": "uncertain",
                "cloudPermitted": False,
            }
        ).model_dump(mode="json")
    
    
    @router.post("/api/access/deletion")
    def post_access_deletion(payload: dict | None = None) -> dict:
        body = payload or {}
        return access_deletion_procedure(
            requested=bool(body.get("requested")),
            controller_recorded=False,
        )
    
    
    @router.post("/api/retention/delete")
    def post_retention_delete(payload: dict | None = None) -> dict:
        body = payload or {}
        kind = str(body.get("kind") or "")
        authorised = bool(body.get("authorisedPolicy"))
        return {
            "kind": kind,
            "mayDelete": may_delete(kind, authorised_policy=authorised),
            "protected": kind in PROTECTED,
        }
    
    
    @router.post("/api/playlists/export-interval")
    def export_playlist_interval(payload: dict | None = None) -> dict:
        body = payload or {}
        try:
            return playlist_export_interval(body, float(body.get("sourceFps") or 25.0))
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    

    return router
