"""Core match read, media, analytics, and correction routes."""

from typing import Annotated

from collections.abc import Callable
import math

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import ValidationError

from .schemas import MatchAnalyticsResponse, MatchFramesResponse, MatchRecord
from .settings import ProcessingSettings
from .segmentation_worker import current_shadow_mask_overlay
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
    def list_matches(request: Request) -> list[dict]:
        matches = storage.list_matches()
        if settings.deployment_mode == "hosted":
            matches = [match for match in matches if match.config.rights.audience == request.state.tenant]
        return [match.model_dump(mode="json") for match in matches]
    
    
    @router.get("/api/matches/{match_id}")
    def get_match(match: Annotated[MatchRecord, Depends(require_match)], generationId: str | None = None) -> dict:
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
    
    
    @router.get("/api/matches/{match_id}/video")
    def get_match_video(match: Annotated[MatchRecord, Depends(require_match)]):
        if match.inputMode != "video":
            raise HTTPException(status_code=409, detail="Video playback is only available for video-backed matches.")
    
        video_path = storage.get_match_input_path(match.id)
        if not video_path.exists():
            raise HTTPException(status_code=404, detail="Video file not found.")
    
        return FileResponse(video_path, media_type="video/mp4", filename=match.originalFilename)

    @router.get("/api/matches/{match_id}/mask-overlay")
    def get_mask_overlay(match: Annotated[MatchRecord, Depends(require_match)], generationId: str = "", frameId: int = 0) -> dict:
        if not generationId or frameId < 0:
            raise HTTPException(status_code=422, detail="Generation and source frame are required")
        try:
            return current_shadow_mask_overlay(storage, match.id, generationId, frameId)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    
    
    @router.get("/api/matches/{match_id}/frames")
    def get_frames(
        match: Annotated[MatchRecord, Depends(require_match)],
        afterFrame: int | None = None,
        cursor: str | None = None,
        limit: int | None = None,
        generationId: str | None = None,
    ) -> dict:
        try:
            with storage.generation_snapshot(match.id, generation_id=generationId) as ref:
                page = storage.load_frames_page(match.id, after_frame=afterFrame, cursor=cursor, limit=limit)
                try:
                    source_clock = storage.load_analysis_artifact(match.id, "source_clock")
                except FileNotFoundError:
                    source_clock = None
                source_fps = source_clock.get("nominalFps") if isinstance(source_clock, dict) else None
                response = MatchFramesResponse(
                    matchId=match.id, frames=page["frames"], nextCursor=page["nextCursor"],
                    frameCount=page["frameCount"], intervalEndpoint=page["intervalEndpoint"],
                    lastFrameId=page["lastFrameId"],
                    sourceFps=source_fps if isinstance(source_fps, (int, float)) and math.isfinite(source_fps) and source_fps > 0 else None,
                ).model_dump(mode="json")
                return {**response, "generationId": ref.generationId}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc
    
    
    @router.get("/api/matches/{match_id}/evidence")
    def get_match_evidence(
        match: Annotated[MatchRecord, Depends(require_match)],
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
    
    
    @router.get("/api/matches/{match_id}/analytics")
    def get_analytics(match: Annotated[MatchRecord, Depends(require_match)], generationId: str | None = None) -> dict:
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
    
    
    @router.post("/api/matches/{match_id}/corrections")
    def post_match_correction(match: Annotated[MatchRecord, Depends(require_match)], payload: dict | None = None) -> dict:
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
    
    
    @router.post("/api/matches/{match_id}/corrections/{correction_id}/recover")
    def recover_match_correction(correction_id: str, match: Annotated[MatchRecord, Depends(require_match)]) -> dict:
        try:
            saved = storage.recover_correction(match.id, correction_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Correction not found") from exc
        return correction_api_payload(saved)
    
    
    @router.post("/api/matches/{match_id}/corrections/{correction_id}/undo")
    def undo_match_correction(correction_id: str, match: Annotated[MatchRecord, Depends(require_match)], payload: dict | None = None) -> dict:
        try:
            body = payload or {}
            saved = storage.undo_correction(match.id, correction_id,
                expected_version=body.get("expectedVersion"), base_generation=body.get("baseGeneration"),
                command_id=body.get("commandId"), idempotency_key=body.get("idempotencyKey"))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Correction not found") from exc
        return correction_api_payload(saved)
    
    
    @router.get("/api/matches/{match_id}/corrections")
    def list_match_corrections(match: Annotated[MatchRecord, Depends(require_match)], state: str | None = None) -> dict:
        return {"items": storage.list_corrections(match.id, state=state)}
    

    return router
