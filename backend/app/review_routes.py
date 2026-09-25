"""Review bundle, annotation, issue, and trust-crop API routes."""

from typing import Annotated

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException

from .numeric_types import is_builtin_number

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


def _trust_crop_geometry(manifest, frames) -> tuple[float | None, float | None, list[str]]:
    declared = all(
        frame.geometryAvailable
        and frame.coordinateSpace == "pitch_normalized_0_100"
        and frame.coordinateProvenance.get("outputConvention") == "pitch_normalized_0_100"
        and isinstance(frame.coordinateProvenance.get("inputConvention"), dict)
        for frame in frames
    )
    if not frames or not declared:
        return None, None, ["CALIBRATION_UNAVAILABLE"]
    conventions = [frame.coordinateProvenance["inputConvention"] for frame in frames]
    config = manifest.effectiveConfig or {}
    length, width = config.get("pitchLengthM"), config.get("pitchWidthM")
    calibration = manifest.calibrationData
    if isinstance(calibration, dict) and calibration.get("accepted") is True and calibration.get("measured") is True:
        length, width = calibration.get("pitchLengthM"), calibration.get("pitchWidthM")
    elif all(item.get("space") == "pitch_metres" for item in conventions):
        dimensions = {(item.get("pitchLengthM"), item.get("pitchWidthM")) for item in conventions}
        if len(dimensions) != 1:
            return None, None, ["CALIBRATION_UNAVAILABLE"]
        length, width = dimensions.pop()
    if not is_builtin_number(length) or not is_builtin_number(width):
        return None, None, ["CALIBRATION_UNAVAILABLE"]
    return float(length), float(width), []


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
    def list_annotations(match: Annotated[MatchRecord, Depends(require_match)]) -> dict:
        """List all annotations for a match."""
        annotations = storage.list_annotations(match.id)
        return {"matchId": match.id, "annotations": [a.model_dump(mode="json") for a in annotations]}

    @router.post("/api/matches/{match_id}/annotations", status_code=201)
    def create_annotation(request: CreateAnnotationRequest, match: Annotated[MatchRecord, Depends(require_match)]) -> dict:
        """Create a new annotation on a match."""
        record = storage.create_annotation(match.id, request)
        return record.model_dump(mode="json")

    @router.delete("/api/matches/{match_id}/annotations/{annotation_id}", status_code=204)
    def delete_annotation(annotation_id: str, match: Annotated[MatchRecord, Depends(require_match)]) -> None:
        """Delete an annotation."""
        try:
            storage.delete_annotation(match.id, annotation_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc

    @router.get("/api/matches/{match_id}/issues")
    def list_issues(match: Annotated[MatchRecord, Depends(require_match)]) -> dict:
        """List all issues for a match."""
        issues = storage.list_issues(match.id)
        return {"matchId": match.id, "issues": [i.model_dump(mode="json") for i in issues]}

    @router.post("/api/matches/{match_id}/issues", status_code=201)
    def create_issue(request: CreateIssueRequest, match: Annotated[MatchRecord, Depends(require_match)]) -> dict:
        """Create a new issue on a match."""
        record = storage.create_issue(match.id, request)
        return record.model_dump(mode="json")

    @router.delete("/api/matches/{match_id}/issues/{issue_id}", status_code=204)
    def delete_issue(issue_id: str, match: Annotated[MatchRecord, Depends(require_match)]) -> None:
        """Delete an issue."""
        try:
            storage.delete_issue(match.id, issue_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc

    @router.get("/api/matches/{match_id}/trust-crops")
    def get_trust_crops(
        match: Annotated[MatchRecord, Depends(require_match)],
        limit: int = 20,
        generationId: str | None = None,
    ) -> dict:
        """Compute heuristic-based trust crop queue for a match.

        Frames are scored by uncertainty: ball teleport distance,
        track ID switch frequency, team flip rate, possession gaps.
        """
        def make_response(frames, assignments, generation_id, manifest=None):
            if manifest is None:
                pitch_length_m, pitch_width_m, geometry_reasons = None, None, ["CALIBRATION_UNAVAILABLE"]
            else:
                pitch_length_m, pitch_width_m, geometry_reasons = _trust_crop_geometry(manifest, frames)
            crops = compute_trust_crops(
                [frame.model_dump() for frame in frames],
                [assignment.model_dump() for assignment in assignments],
                max_crops=limit,
                pitch_length_m=pitch_length_m,
                pitch_width_m=pitch_width_m,
            )
            return TrustCropsResponse(
                matchId=match.id,
                generationId=generation_id,
                ballTeleportGeometryAvailable=not geometry_reasons,
                ballTeleportReasonCodes=geometry_reasons,
                crops=[TrustCropSchema(
                    frameStart=crop.frameStart, frameEnd=crop.frameEnd,
                    timestampStart=crop.timestampStart, timestampEnd=crop.timestampEnd,
                    score=crop.score, reasons=crop.reasons,
                ) for crop in crops],
                totalFrames=len(frames),
            )

        try:
            with storage.generation_snapshot(match.id, generation_id=generationId) as ref:
                frames = storage.load_frames(match.id, generation_id=ref.generationId)
                _summary, assignments, _, _ = storage.load_analytics(
                    match.id, generation_id=ref.generationId
                )
                manifest, _ = storage.generations.manifest(match.id, ref.generationId)
                response = make_response(frames, assignments, ref.generationId, manifest)
        except FileNotFoundError as exc:
            if generationId is not None:
                raise HTTPException(status_code=404, detail="Frames or analytics not ready") from exc
            try:
                frames = storage.load_frames(match.id)
                _summary, assignments, _, _ = storage.load_analytics(match.id)
                response = make_response(frames, assignments, None)
            except FileNotFoundError as legacy_exc:
                raise HTTPException(status_code=404, detail="Frames or analytics not ready") from legacy_exc
        return response.model_dump(mode="json")

    return router
