"""Review bundle, annotation, issue, and trust-crop API routes."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException

from .schemas import (
    CreateAnnotationRequest,
    CreateBundleRequest,
    CreateIssueRequest,
    MatchRecord,
    ReviewBundleItem,
    TrustCropSchema,
    TrustCropsResponse,
    UpdateBundleRequest,
)
from .storage import Storage
from .trust_crops import compute_trust_crops


def create_review_router(
    storage: Storage,
    require_match: Callable[..., MatchRecord],
) -> APIRouter:
    router = APIRouter()

    # ===== Review Bundles / Playlists =====

    @router.get("/api/bundles")
    def list_bundles(tags: str | None = None) -> list[dict]:
        """List all bundles, optionally filtered by tags (comma-separated)."""
        tag_list = tags.split(",") if tags else None
        return [b.model_dump(mode="json") for b in storage.list_review_bundles(tag_list)]

    @router.get("/api/bundles/{bundle_id}")
    def get_bundle(bundle_id: str) -> dict:
        """Get a single bundle by ID."""
        try:
            return storage.get_review_bundle(bundle_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Bundle not found") from exc

    @router.post("/api/bundles", status_code=201)
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

    @router.put("/api/bundles/{bundle_id}")
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

    @router.delete("/api/bundles/{bundle_id}", status_code=204)
    def delete_bundle(bundle_id: str) -> None:
        """Delete a bundle."""
        try:
            storage.delete_review_bundle(bundle_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Bundle not found") from exc

    # ===== Annotations & Issues =====

    @router.get("/api/matches/{match_id}/annotations")
    def list_annotations(match: MatchRecord = Depends(require_match)) -> dict:
        """List all annotations for a match."""
        annotations = storage.list_annotations(match.id)
        return {"matchId": match.id, "annotations": [a.model_dump(mode="json") for a in annotations]}

    @router.post("/api/matches/{match_id}/annotations", status_code=201)
    def create_annotation(request: CreateAnnotationRequest, match: MatchRecord = Depends(require_match)) -> dict:
        """Create a new annotation on a match."""
        record = storage.create_annotation(match.id, request)
        return record.model_dump(mode="json")

    @router.delete("/api/matches/{match_id}/annotations/{annotation_id}", status_code=204)
    def delete_annotation(annotation_id: str, match: MatchRecord = Depends(require_match)) -> None:
        """Delete an annotation."""
        try:
            storage.delete_annotation(match.id, annotation_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc

    @router.get("/api/matches/{match_id}/issues")
    def list_issues(match: MatchRecord = Depends(require_match)) -> dict:
        """List all issues for a match."""
        issues = storage.list_issues(match.id)
        return {"matchId": match.id, "issues": [i.model_dump(mode="json") for i in issues]}

    @router.post("/api/matches/{match_id}/issues", status_code=201)
    def create_issue(request: CreateIssueRequest, match: MatchRecord = Depends(require_match)) -> dict:
        """Create a new issue on a match."""
        record = storage.create_issue(match.id, request)
        return record.model_dump(mode="json")

    @router.delete("/api/matches/{match_id}/issues/{issue_id}", status_code=204)
    def delete_issue(issue_id: str, match: MatchRecord = Depends(require_match)) -> None:
        """Delete an issue."""
        try:
            storage.delete_issue(match.id, issue_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc

    @router.get("/api/matches/{match_id}/trust-crops")
    def get_trust_crops(
        match: MatchRecord = Depends(require_match),
        limit: int = 20,
        generationId: str | None = None,
    ) -> dict:
        """Compute heuristic-based trust crop queue for a match.

        Frames are scored by uncertainty: ball teleport distance,
        track ID switch frequency, team flip rate, possession gaps.
        """
        try:
            with storage.generation_snapshot(match.id, generation_id=generationId) as ref:
                frames = storage.load_frames(match.id, generation_id=ref.generationId)
                _summary, assignments, _, _ = storage.load_analytics(
                    match.id, generation_id=ref.generationId
                )
                frames_dicts = [f.model_dump() for f in frames]
                assignments_dicts = [a.model_dump() for a in assignments]
                crops = compute_trust_crops(
                    frames_dicts, assignments_dicts, max_crops=limit
                )
                response = TrustCropsResponse(
                    matchId=match.id,
                    generationId=ref.generationId,
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
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames or analytics not ready") from exc
        return response.model_dump(mode="json")

    return router
