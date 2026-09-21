"""Match detail, diagnostic, report, and analysis routes."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from .provider_gateway import ProviderDenied, ProviderGateway
from .run_benchmarks import summarize_match_benchmark
from .schemas import MatchRecord
from .storage import Storage
from .workbench.errors import DomainError
from .workbench.review import correction_api_payload


def create_match_detail_router(
    storage: Storage,
    require_match: Callable[..., MatchRecord],
    snapshot_response: Callable[..., dict],
    provider_gateway: ProviderGateway,
) -> APIRouter:
    router = APIRouter()

    @router.post("/api/matches/{match_id}/queries")
    def post_match_query(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        return snapshot_response(match.id, lambda: storage.query_match_events(match.id, str(body.get("query") or "")), body.get("generationId"))
    
    @router.post("/api/matches/{match_id}/reports")
    def post_match_report(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        claimed = body.get("claimedEvidenceIds")
        try:
            return storage.assemble_match_report(
                match.id,
                claimed_evidence_ids=claimed,
                narrative=body.get("narrative"),
                generation_id=body.get("generationId"),
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc
    
    @router.get("/api/matches/{match_id}/heatmap")
    def get_match_heatmap(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        return snapshot_response(match.id, lambda: storage.heatmap_for_match(match.id), generationId)
    
    @router.get("/api/matches/{match_id}/players")
    def get_match_players(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        try:
            return snapshot_response(match.id, lambda: storage.player_observations_for_match(match.id), generationId)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc
    
    @router.get("/api/matches/{match_id}/ownership")
    def get_match_ownership(match: MatchRecord = Depends(require_match)) -> dict:
        try:
            return storage.classify_match_ownership(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc
    
    @router.get("/api/matches/{match_id}/package")
    def get_match_package(match: MatchRecord = Depends(require_match)) -> dict:
        try:
            return storage.assemble_stored_match_package(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc
    
    @router.get("/api/matches/{match_id}/incidents/geometry")
    def get_match_incident_geometry(match: MatchRecord = Depends(require_match)) -> dict:
        try:
            return storage.incident_geometry_for_match(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc
    
    @router.get("/api/matches/{match_id}/setup")
    def match_setup(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        return snapshot_response(match.id, lambda: storage.assess_stored_match_setup(match.id), generationId)
    
    @router.get("/api/matches/{match_id}/rates")
    def match_rates(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.four_rates_for_match(match.id)
    
    @router.get("/api/matches/{match_id}/metrics")
    def get_match_metrics(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        try:
            return snapshot_response(match.id, lambda: storage.match_metrics_for_match(match.id), generationId)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc
    
    @router.get("/api/matches/{match_id}/metrics/inspect/{metric}")
    def inspect_stored_metric(metric: str, match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        try:
            return snapshot_response(match.id, lambda: storage.inspect_match_metric(match.id, metric), generationId)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc
    
    @router.get("/api/matches/{match_id}/incidents/package")
    def get_match_incident_package(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.incident_package_for_match(match.id)
    
    @router.get("/api/matches/{match_id}/clock")
    def get_match_clock(match: MatchRecord = Depends(require_match)) -> dict:
        try:
            return storage.clock_for_match(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc
    
    @router.get("/api/matches/{match_id}/incidents/review")
    def get_match_incident_review(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        try:
            return snapshot_response(match.id, lambda: storage.incident_review_for_match(match.id), generationId)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc
    
    @router.get("/api/matches/{match_id}/privacy")
    def get_match_privacy(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.dpia_for_match(match.id)
    
    @router.get("/api/matches/{match_id}/setup/preview")
    def get_match_setup_preview(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        return snapshot_response(match.id, lambda: storage.preview_landmark_for_match(match.id), generationId)
    
    @router.post("/api/matches/{match_id}/calibration/commit")
    def commit_match_calibration(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        return storage.commit_calibration_for_match(match.id, payload or {})
    
    @router.post("/api/matches/{match_id}/recompute")
    def post_match_recompute(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        return storage.recompute_for_match(match.id, str(body.get("change") or "report"))
    
    @router.post("/api/matches/{match_id}/recompute/execute")
    def post_match_recompute_execute(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        return storage.execute_recompute(match.id, str(body.get("change") or "report")).model_dump(mode="json")
    
    @router.get("/api/matches/{match_id}/promotion")
    def get_match_promotion(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.promotion_receipt_for_match(match.id)
    
    @router.get("/api/matches/{match_id}/quality")
    def get_match_quality(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        return snapshot_response(match.id, lambda: storage.quality_timeline_for_match(match.id), generationId)
    
    @router.get("/api/matches/{match_id}/identity")
    def get_match_identity(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        return snapshot_response(match.id, lambda: storage.identity_for_match(match.id), generationId)
    
    @router.post("/api/matches/{match_id}/identity/repair")
    def post_match_identity_repair(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        return storage.repair_identity_for_match(match.id, payload)
    
    @router.post("/api/matches/{match_id}/identity/promote")
    def post_match_identity_promote(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        return storage.promote_identity_for_match(match.id, payload)
    
    @router.get("/api/matches/{match_id}/history")
    def get_match_history(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.history_for_match(match.id)
    
    @router.get("/api/matches/{match_id}/cache")
    def get_match_cache(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.cache_identity_for_match(match.id)
    
    @router.get("/api/matches/{match_id}/records/migrate")
    def get_match_legacy_migrate(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.migrate_legacy_for_match(match.id)
    
    @router.get("/api/matches/{match_id}/attack-direction")
    def get_match_attack_direction(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.attack_direction_for_match(match.id, team="my_team", period=1)
    
    @router.post("/api/matches/{match_id}/attack-direction")
    def post_match_attack_direction(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        return storage.attack_direction_for_match(
            match.id,
            team=str(body.get("team") or "my_team"),
            period=int(body.get("period") or 1),
        )
    
    @router.get("/api/matches/{match_id}/calibration")
    def get_match_calibration(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.calibration_for_match(match.id)
    
    @router.post("/api/matches/{match_id}/calibration")
    def post_match_calibration(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        return storage.calibration_for_match(match.id, payload)
    
    @router.get("/api/matches/{match_id}/formation")
    def get_match_formation(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        return snapshot_response(match.id, lambda: storage.formation_for_match(match.id), generationId)
    
    @router.get("/api/matches/{match_id}/events/partition")
    def get_match_event_partition(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.partition_events_for_match(match.id)
    
    @router.get("/api/matches/{match_id}/reports/provenance")
    def get_match_report_provenance(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.provenance_for_match(match.id)
    
    @router.get("/api/matches/{match_id}/reports/coverage")
    def get_match_report_coverage(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        return snapshot_response(match.id, lambda: storage.coverage_for_match(match.id), generationId)
    
    @router.get("/api/matches/{match_id}/shots/quality")
    def get_match_shot_quality(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.shot_quality_for_match(match.id)
    
    @router.get("/api/matches/{match_id}/media/proxy")
    def get_match_proxy(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.proxy_assets_for_match(match.id)
    
    @router.get("/api/matches/{match_id}/edits")
    def get_match_edits(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        return storage.edit_list_for_match(match.id, generation_id=generationId)
    
    @router.post("/api/matches/{match_id}/edits/render")
    def post_match_edit_render(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        return storage.render_edit_for_match(
            match.id,
            start=float(body.get("start") or 0.0),
            end=float(body.get("end") or 0.0),
            generation_id=body.get("generationId"),
        )
    
    @router.get("/api/matches/{match_id}/tracklets")
    def get_match_tracklets(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.tracklets_for_match(match.id)
    
    @router.get("/api/matches/{match_id}/geometry/distance")
    def get_match_derived_distance(match: MatchRecord = Depends(require_match), generationId: str | None = None) -> dict:
        return snapshot_response(match.id, lambda: storage.derived_distance_for_match(match.id), generationId)
    
    @router.get("/api/matches/{match_id}/shots/features")
    def get_match_shot_features(match: MatchRecord = Depends(require_match)) -> dict:
        return storage.shot_features_for_match(match.id)
    
    @router.post("/api/matches/{match_id}/recovery/import")
    def post_match_corrupted_import(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        return storage.corrupted_import_for_match(match.id, str(body.get("actualSha256") or ""))
    
    @router.post("/api/matches/{match_id}/assistance/report")
    def post_match_assistance_report(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        claimed = body.get("claimedEvidenceIds")
        try:
            return storage.assemble_match_report(
                match.id,
                claimed_evidence_ids=claimed,
                narrative=body.get("narrative"),
                generation_id=body.get("generationId"),
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc
    
    @router.post("/api/matches/{match_id}/analysis/{analysis_type}")
    def analyze_match(analysis_type: str, match: MatchRecord = Depends(require_match), body: dict | None = None) -> dict:
        match_id = match.id
        body = body or {}
        if analysis_type in {"offside", "spacing"}:
            return storage.incident_geometry_for_match(match_id)
        try:
            result = provider_gateway.execute(
                match_id,
                analysis_type,
                requested_provider=body.get("provider"),
                body=body,
            )
        except DomainError:
            raise
        except ProviderDenied as exc:
            raise HTTPException(status_code=403, detail={"reasonCodes": exc.reason_codes}) from exc
        except (KeyError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    
        return result
    
    @router.get("/api/matches/{match_id}/benchmark")
    def get_match_benchmark(match: MatchRecord = Depends(require_match), includeSelectedClusterProbe: bool = False,
                            generationId: str | None = None) -> dict:
        try:
            with storage.generation_snapshot(match.id, generation_id=generationId) as ref:
                summary = summarize_match_benchmark(storage, match.id)
                from .run_benchmarks import build_snapshot_cluster_payload
                response = summary.model_dump(mode="json") if not includeSelectedClusterProbe else {
                    "saved": summary.model_dump(mode="json"),
                    **build_snapshot_cluster_payload(summary, storage.get_match(match.id))}
                return {**response, "matchId": match.id, "generationId": ref.generationId,
                        "diagnosticProvenance": "flat_diagnostics_unverified_source_binding"}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Benchmark not ready") from exc
    
    @router.patch("/api/matches/{match_id}/config")
    def update_match_config(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        from .review_service import ReviewService
        try:
            _config, command = ReviewService(storage).configure(match.id, payload or {})
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors(include_context=False, include_input=False)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=409, detail="Required match artifacts are not available for reprocessing.") from exc
        if command is not None and command.appliedGeneration is not None:
            with storage.generation_snapshot(match.id, generation_id=command.appliedGeneration):
                response = storage.get_match(match.id).model_dump(mode="json")
            response["correction"] = correction_api_payload(command)
            response["generationId"] = command.appliedGeneration
            return response
        response = storage.get_match(match.id).model_dump(mode="json")
        if command is not None:
            response["correction"] = correction_api_payload(command)
            response["generationId"] = None
        return response

    return router
