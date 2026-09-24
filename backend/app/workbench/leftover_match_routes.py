from __future__ import annotations
from fastapi import APIRouter, Depends, Header, HTTPException
from ..schemas import MatchRecord
from ..storage import Storage
from .access import object_access_decision
from .leftover_support import (
    _challenger_adapters_view,
    _four_rates_view,
    _production_job_request,
    _stale_permissions_view,
    _unpromoted_receipt,
)
from ..ai_policy import (
    ground_output,
    select_evidence,
)
from .access import (
    signed_scoped_object_access,
)
from .assistance import (
    template_report,
)
from .contracts import (
    migrate_legacy_zero,
)
from .dossier import (
    build_baseline_dossier,
    build_release_dossier,
)
from .events import (
    ownership_invalidation,
)
from .evidence import (
    DEFINITION_VERSION,
)
from .jobs import (
    cleanup_failure_is_complete,
    worker_environment,
)
from .ownership import (
    OwnershipHysteresis,
    possession_from_states,
)
from .quantities import (
    heatmap_availability,
    split_scores,
)
from .reports import (
    assemble_report,
)
from .training import (
    experiment_cycle,
    promote_candidate,
    pseudo_label,
)

def register_evidence_post_routes(router: APIRouter, storage: Storage) -> None:
    @router.post("/challengers")
    def post_challengers(payload: dict | None = None) -> dict:
        del payload
        return _challenger_adapters_view()


    @router.post("/permissions/stale")
    def post_stale_permissions(payload: dict | None = None) -> dict:
        del payload
        return _stale_permissions_view()


    @router.post("/heatmap")
    def post_heatmap(payload: dict | None = None) -> dict:
        del payload
        return heatmap_availability(identity_continuous=False)


    @router.post("/reports/assemble")
    def post_assemble_report(payload: dict | None = None) -> dict:
        body = payload or {}
        claimed = list(body.get("claimedEvidenceIds") or [])
        return assemble_report(
            metrics=[],
            events=[],
            claimed_evidence_ids=claimed,
            known_evidence_ids=set(),
        )


    @router.post("/assistance/ground")
    def post_ground_output(payload: dict | None = None) -> dict:
        body = payload or {}
        claimed = list(body.get("evidence") or body.get("claimedEvidenceIds") or [])
        return ground_output({"evidence": claimed}, known_ids=set())


    @router.post("/assistance/select-evidence")
    def post_select_evidence(payload: dict | None = None) -> dict:
        body = payload or {}
        claimed = list(body.get("claimedIds") or body.get("claimedEvidenceIds") or [])
        try:
            evidence = select_evidence(claimed, known_ids=set())
        except ValueError:
            return {"accepted": False, "evidence": [], "reasonCodes": ["FABRICATED_EVIDENCE"]}
        return {"accepted": True, "evidence": evidence, "reasonCodes": ["GROUNDED"]}


    @router.post("/metrics/legacy-zero")
    def post_legacy_zero(payload: dict | None = None) -> dict:
        body = payload or {}
        migrated = migrate_legacy_zero(
            str(body.get("metric") or "possession_pct"),
            body.get("value"),
            definition_version=DEFINITION_VERSION,
            measured=False,
            reason_if_unmeasured="UNMEASURED_LEGACY_DEFAULT",
        )
        return migrated.model_dump(mode="json")


    @router.post("/dossier/release")
    def post_release_dossier(payload: dict | None = None) -> dict:
        del payload
        return build_release_dossier(build_baseline_dossier(), loopback_only=True)


    @router.post("/rates/four")
    def post_four_rates(payload: dict | None = None) -> dict:
        del payload
        return _four_rates_view()


    @router.post("/ownership/hysteresis")
    def post_ownership_hysteresis(payload: dict | None = None) -> dict:
        del payload
        hyst = OwnershipHysteresis(min_persistence=3)
        return {"owner": hyst.observe("my_team"), "minPersistence": 3}


    @router.post("/metrics/possession-states")
    def post_possession_states(payload: dict | None = None) -> dict:
        body = payload or {}
        summary = possession_from_states(list(body.get("states") or []), float(body.get("requestedSeconds") or 0.0))
        dumped = summary.model_dump(mode="json")
        dumped["publishedValue"] = summary.published_value()
        return dumped


    @router.post("/reports/template")
    def post_template_report(payload: dict | None = None) -> dict:
        del payload
        return template_report([], [])


    @router.post("/receipts/promotion")
    def post_promotion_receipt(payload: dict | None = None) -> dict:
        del payload
        return _unpromoted_receipt()


    @router.post("/ownership/invalidate")
    def post_ownership_invalidate(payload: dict | None = None) -> dict:
        del payload
        return {"change": "track_edit", "invalidates": ownership_invalidation()}


    @router.post("/quantities/scores")
    def post_split_scores(payload: dict | None = None) -> dict:
        body = payload or {}
        interval = body.get("interval")
        return split_scores(
            detector_score=body.get("detectorScore"),
            calibrated_probability=body.get("calibratedProbability"),
            interval=tuple(interval) if interval else None,
        )


    @router.post("/worker/environment")
    def post_worker_environment(payload: dict | None = None) -> dict:
        del payload
        return worker_environment(_production_job_request(), host_secret="")


    @router.post("/cleanup/complete")
    def post_cleanup_complete(payload: dict | None = None) -> dict:
        del payload
        return {"complete": cleanup_failure_is_complete("failed"), "cleanupResult": "failed"}


    @router.post("/upload/interrupt")
    def post_upload_interrupt(payload: dict | None = None) -> dict:
        del payload
        return storage.interrupted_upload_run()


    @router.post("/access/signed")
    def post_signed_object_access(payload: dict | None = None) -> dict:
        del payload
        return signed_scoped_object_access(token=None, object_id="", token_object_id=None)


    @router.post("/training/cycle")
    def post_training_cycle(payload: dict | None = None) -> dict:
        body = payload or {}
        return experiment_cycle(
            str(body.get("stage") or "diagnose"),
            measurable_failure=False,
            budget_remaining=0.0,
            development_benefit=False,
            gate_regressed=True,
        )


    @router.post("/training/promote")
    def post_training_promote(payload: dict | None = None) -> dict:
        del payload
        return promote_candidate(independent_accepted=False, rollback_artifact=True)


    @router.post("/training/pseudo")
    def post_training_pseudo(payload: dict | None = None) -> dict:
        body = payload or {}
        return pseudo_label(suggestion=str(body.get("suggestion") or ""), human_change=None, approved=False)



def register_match_post_routes(router: APIRouter, storage: Storage) -> None:
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


    @router.post("/search")
    def post_typed_search(payload: dict | None = None) -> dict:
        body = payload or {}
        match_id = str(body.get("matchId") or "")
        if not match_id:
            raise HTTPException(status_code=400, detail="matchId is required")
        try:
            match = storage.get_match(match_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc
        del match
        result = storage.query_match_events(
            match_id,
            str(body.get("query") or ""),
            include_unknown=body.get("includeUnknown") is True,
        )
        if body.get("strict") is True and result["unsupportedTerms"]:
            raise HTTPException(
                status_code=422,
                detail={"unsupportedTerms": result["unsupportedTerms"], "interpreted": result["interpreted"]},
            )
        return result


    @router.post("/matches/{match_id}/heatmap")
    def post_match_heatmap(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.heatmap_for_match(match.id)


    @router.post("/matches/{match_id}/players")
    def post_match_players(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        try:
            return storage.player_observations_for_match(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc


    @router.post("/matches/{match_id}/ownership")
    def post_match_ownership(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        try:
            return storage.classify_match_ownership(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc


    @router.post("/matches/{match_id}/package")
    def post_match_package(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        try:
            return storage.assemble_stored_match_package(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc


    @router.post("/matches/{match_id}/incidents/geometry")
    def post_match_incident_geometry(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        try:
            return storage.incident_geometry_for_match(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc


    @router.post("/matches/{match_id}/metrics")
    def post_match_metrics(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        try:
            return storage.match_metrics_for_match(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc


    @router.post("/matches/{match_id}/incidents/package")
    def post_match_incident_package(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.incident_package_for_match(match.id)


    @router.post("/matches/{match_id}/incidents/review")
    def post_match_incident_review(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        try:
            return storage.incident_review_for_match(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Frames not ready") from exc


    @router.post("/matches/{match_id}/assistance/fallback")
    def post_match_assistance_fallback(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        try:
            return storage.assistance_fallback_for_match(match.id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc


    @router.post("/matches/{match_id}/identity")
    def post_match_identity(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.identity_for_match(match.id)


    @router.post("/matches/{match_id}/cache")
    def post_match_cache(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.cache_identity_for_match(match.id)


    @router.post("/matches/{match_id}/records/migrate")
    def post_match_legacy_migrate(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.migrate_legacy_for_match(match.id)


    @router.post("/matches/{match_id}/formation")
    def post_match_formation(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.formation_for_match(match.id)


    @router.post("/matches/{match_id}/events/partition")
    def post_match_event_partition(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.partition_events_for_match(match.id)


    @router.post("/matches/{match_id}/reports/provenance")
    def post_match_report_provenance(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        body = payload or {}
        claimed = body.get("claims")
        claimed_ids: list[str] | None = None
        if isinstance(claimed, list):
            claimed_ids = [
                evidence_id
                for claim in claimed
                if isinstance(claim, dict)
                for evidence_id in (claim.get("evidenceIds") or [])
            ]
        elif body.get("claimedEvidenceIds") is not None:
            claimed_ids = list(body.get("claimedEvidenceIds") or [])
        return storage.provenance_for_match(match.id, claimed_evidence_ids=claimed_ids)


    @router.post("/matches/{match_id}/shots/quality")
    def post_match_shot_quality(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.shot_quality_for_match(match.id)


    @router.post("/matches/{match_id}/artifacts/alongside")
    def post_match_write_alongside(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.write_alongside_for_match(match.id)


    @router.post("/matches/{match_id}/tracklets")
    def post_match_tracklets(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.tracklets_for_match(match.id)


    @router.post("/matches/{match_id}/shots/features")
    def post_match_shot_features(match: MatchRecord = Depends(require_match), payload: dict | None = None) -> dict:
        del payload
        return storage.shot_features_for_match(match.id)
