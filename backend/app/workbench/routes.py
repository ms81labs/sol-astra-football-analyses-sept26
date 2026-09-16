"""HTTP surface for the v1.1 workbench."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .admission import admit_camera, admit_media
from .assistance import AssistancePolicy, AssistanceRouter, execute_typed_query, parse_typed_query
from .contracts import SourceClockIdentity, jsonable
from .costs import credit_allocation, match_cost
from .dossier import build_baseline_dossier, build_release_dossier
from .evaluation import current_repository_evaluation_gate
from .evidence import EvidenceStore, inspect_metric, metric_dictionary, summarize_legacy_match
from .flags import feature_flags
from .geometry import review_incident_geometry
from .identity import player_observations
from .incidents import level0_incident_package
from .jobs import DurableJobLedger, JobRequest
from .library import search_match_library
from .media import FourRatesReceipt
from .milestones import milestone_plan, owners, progress_signal
from .native import native_gate, probe_gpu
from .ownership import classify_ownership
from .package import assemble_match_package
from .privacy import residency_claim
from .reports import assemble_report
from .review import CorrectionLog, new_correction, playlist_export_interval
from .rights import rights_register
from .risks import risk_register
from .roster import model_roster
from .setup import assess_match_setup, create_match
from .store import WorkbenchStore
from .targets import metadata_api_targets
from .training import drill_library
from .xt import xt_deferred_plan

_correction_log = CorrectionLog()
_job_ledger = DurableJobLedger()
_router_assistance = AssistanceRouter(providers_enabled=False)
_evidence_store = EvidenceStore()


class CorrectionBody(BaseModel):
    kind: str
    payload: dict = Field(default_factory=dict)
    author: str = "analyst"
    crashBeforeCommit: bool = False
    expectedVersion: int | None = None


class SearchBody(BaseModel):
    query: str
    matchId: str
    events: list[dict] = Field(default_factory=list)


class AssistanceBody(BaseModel):
    metrics: list[dict] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)
    claimedEvidenceIds: list[str] = Field(default_factory=list)
    knownEvidenceIds: list[str] = Field(default_factory=list)


class JobBody(BaseModel):
    requestId: str
    matchId: str
    sourceSha256: str
    intervalStart: float = 0.0
    intervalEnd: float = 0.0
    temporalPolicy: str = "clip_local_index_modulo"
    decoderVersion: str = "opencv"
    modelHash: str = "unspecified"
    outputSchema: str = "evidence_v1"
    budget: float = 0.0
    authorisedLocation: str = "local"


class QueryBody(BaseModel):
    query: str
    events: list[dict] = Field(default_factory=list)


class ReportBody(BaseModel):
    metrics: list[dict] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)
    claimedEvidenceIds: list[str] = Field(default_factory=list)
    knownEvidenceIds: list[str] = Field(default_factory=list)


class MediaAdmitBody(BaseModel):
    sourceSha256: str
    byteSize: int
    codec: str | None = None
    audioTracks: int = 0
    decodeErrors: list[str] = Field(default_factory=list)
    variableFrameRate: bool = False
    rotation: int = 0
    requireAudio: bool = False
    existingDigests: list[str] = Field(default_factory=list)


class LibrarySearchBody(BaseModel):
    query: str
    matches: list[dict] = Field(default_factory=list)


class PlayerBody(BaseModel):
    rows: list[dict] = Field(default_factory=list)
    identityContinuous: bool = False


_CORRECTION_INVALIDATION = {
    "team_mapping": "team_mapping",
    "track_split": "track_edit",
    "track_join": "track_edit",
    "event_reject": "ownership",
    "event_accept": "ownership",
    "ownership": "ownership",
    "calibration": "calibration",
    "playlist_item": "report",
}


def _correction_response(saved) -> dict:
    payload = jsonable(saved)
    if saved.saveState == "saved":
        change = _CORRECTION_INVALIDATION.get(saved.kind, "report")
        payload["rebuild"] = _job_ledger.invalidate_for(change)  # type: ignore[arg-type]
    else:
        payload["rebuild"] = []
    return payload


def create_workbench_router(storage_root: Path) -> APIRouter:
    store = WorkbenchStore(storage_root)
    router = APIRouter(prefix="/api/workbench", tags=["workbench"])

    @router.get("/dossier")
    def get_dossier() -> dict:
        dossier = build_baseline_dossier()
        store.save_dossier(dossier)
        return {
            "baseline": jsonable(dossier),
            "release": build_release_dossier(dossier),
            "evaluation": jsonable(current_repository_evaluation_gate()),
            "gpu": jsonable(probe_gpu()),
            "native": jsonable(native_gate(repo_root=Path(__file__).resolve().parents[3])),
        }

    @router.get("/capabilities")
    def get_capabilities() -> dict:
        dossier = build_baseline_dossier()
        return {"capabilities": [jsonable(entry) for entry in dossier.capabilities]}

    @router.post("/matches/{match_id}/corrections")
    def post_correction(match_id: str, body: CorrectionBody) -> dict:
        correction = new_correction(match_id, body.kind, body.payload, author=body.author)  # type: ignore[arg-type]
        saved = _correction_log.submit(
            correction,
            crash_before_commit=body.crashBeforeCommit,
            expected_version=body.expectedVersion,
        )
        if saved.saveState == "saved":
            store.append_correction(saved)
        return _correction_response(saved)

    @router.post("/matches/{match_id}/corrections/{correction_id}/recover")
    def recover_correction(match_id: str, correction_id: str) -> dict:
        saved = _correction_log.recover(correction_id)
        if saved.matchId != match_id:
            raise HTTPException(status_code=404, detail="Correction not found")
        store.append_correction(saved)
        return _correction_response(saved)

    @router.post("/matches/{match_id}/corrections/{correction_id}/undo")
    def undo_correction(match_id: str, correction_id: str) -> dict:
        undone = _correction_log.undo(correction_id, author="analyst")
        store.append_correction(undone)
        return _correction_response(undone)

    @router.get("/matches/{match_id}/corrections")
    def list_corrections(match_id: str, state: str | None = None) -> dict:
        items = _correction_log.pending(match_id) if state == "pending" else _correction_log.history(match_id)
        return {"items": [jsonable(item) for item in items]}

    @router.post("/matches/{match_id}/queries")
    def match_queries(match_id: str, body: QueryBody) -> dict:
        query = parse_typed_query(body.query)
        hits = execute_typed_query(body.events, query, match_id=match_id)
        return {"query": jsonable(query), "results": [jsonable(hit) for hit in hits]}

    @router.post("/matches/{match_id}/reports")
    def match_reports(match_id: str, body: ReportBody) -> dict:
        disposition = _router_assistance.run(
            policy=AssistancePolicy(taskType="report", spendCap=0.0, allowedModelIds=[]),
            metrics=body.metrics,
            events=body.events,
            claimed_evidence_ids=body.claimedEvidenceIds,
            known_evidence_ids=set(body.knownEvidenceIds),
        )
        return jsonable(disposition)

    @router.post("/playlists/export-interval")
    def export_interval(payload: dict) -> dict:
        return playlist_export_interval(payload, float(payload.get("sourceFps") or 25.0))

    @router.post("/search")
    def typed_search(body: SearchBody) -> dict:
        query = parse_typed_query(body.query)
        hits = execute_typed_query(body.events, query, match_id=body.matchId)
        return {"query": jsonable(query), "results": [jsonable(hit) for hit in hits]}

    @router.post("/assistance/report")
    def assistance_report(body: AssistanceBody) -> dict:
        disposition = _router_assistance.run(
            policy=AssistancePolicy(taskType="report", spendCap=0.0, allowedModelIds=[]),
            metrics=body.metrics,
            events=body.events,
            claimed_evidence_ids=body.claimedEvidenceIds,
            known_evidence_ids=set(body.knownEvidenceIds),
        )
        return jsonable(disposition)

    @router.post("/jobs")
    def create_job(body: JobBody) -> dict:
        request = JobRequest(
            requestId=body.requestId,
            matchId=body.matchId,
            sourceSha256=body.sourceSha256,
            intervalStart=body.intervalStart,
            intervalEnd=body.intervalEnd,
            temporalPolicy=body.temporalPolicy,
            decoderVersion=body.decoderVersion,
            modelHash=body.modelHash,
            outputSchema=body.outputSchema,
            budget=body.budget,
            authorisedLocation="local" if body.authorisedLocation != "daytona" else "daytona",
        )
        attempt = _job_ledger.submit(request)
        return jsonable(_job_ledger.receipt(body.requestId)) | {"attemptId": attempt.attemptId}

    @router.post("/jobs/{request_id}/timeout")
    def job_timeout(request_id: str) -> dict:
        _job_ledger.timeout_before_response(request_id)
        return jsonable(_job_ledger.receipt(request_id))

    @router.post("/jobs/{request_id}/cancel")
    def job_cancel(request_id: str) -> dict:
        _job_ledger.cancel(request_id)
        return jsonable(_job_ledger.receipt(request_id))

    @router.post("/matches/{match_id}/metrics")
    def match_metrics(match_id: str, payload: dict | None = None) -> dict:
        del match_id
        body = payload or {}
        metrics = summarize_legacy_match(
            body,
            identity_continuous=bool(body.get("identityContinuous")),
            calibration_accepted=bool(body.get("calibrationAccepted")),
            controlled_frames=int(body.get("controlledFrames") or 0),
        )
        return {"metrics": [jsonable(metric) for metric in metrics]}

    @router.get("/metrics/dictionary")
    def get_metric_dictionary() -> dict:
        return {"metrics": metric_dictionary()}

    @router.get("/matches/{match_id}/evidence")
    def get_evidence(
        match_id: str,
        intervalStart: float | None = None,
        intervalEnd: float | None = None,
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict:
        del match_id
        page = _evidence_store.query(
            interval_start=intervalStart,
            interval_end=intervalEnd,
            cursor=cursor,
            limit=limit,
        )
        return jsonable(page)

    @router.post("/matches/{match_id}/incidents/geometry")
    def incident_geometry(match_id: str, payload: dict | None = None) -> dict:
        del match_id
        body = payload or {}
        return review_incident_geometry(
            my_team=list(body.get("myTeam") or []),
            enemies=list(body.get("enemies") or []),
            ball=body.get("ball"),
            attack_direction=body.get("attackDirection") or "left_to_right",
        )

    @router.get("/jobs/{request_id}")
    def get_job(request_id: str) -> dict:
        try:
            receipt = jsonable(_job_ledger.receipt(request_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
        receipt["cancelRequested"] = _job_ledger.cancel_requested(request_id)
        receipt["terminated"] = _job_ledger.terminated(request_id)
        return receipt

    @router.get("/jobs/{request_id}/cost")
    def job_cost(request_id: str) -> dict:
        del request_id
        return _job_ledger.cost_summary()

    @router.get("/flags")
    def get_flags() -> dict:
        return feature_flags()

    @router.post("/matches/{match_id}/ownership")
    def match_ownership(match_id: str, payload: dict | None = None) -> dict:
        del match_id
        body = payload or {}
        return jsonable(
            classify_ownership(
                ball_visible=bool(body.get("ballVisible", True)),
                nearest_team=body.get("nearestTeam"),
                nearest_distance=body.get("nearestDistance"),
                relative_motion=body.get("relativeMotion"),
                persistence_frames=int(body.get("persistenceFrames") or 0),
                calibrated=bool(body.get("calibrated")),
            )
        )

    @router.post("/matches/{match_id}/package")
    def match_package(match_id: str, payload: dict | None = None) -> dict:
        del match_id
        body = payload or {}
        return assemble_match_package(
            playlist=list(body.get("playlist") or []),
            events=list(body.get("events") or []),
            metrics=list(body.get("metrics") or []),
            corrections=list(body.get("corrections") or []),
            cost=body.get("cost") or {},
            secrets=body.get("secrets") or {},
        )

    @router.get("/rights")
    def get_rights() -> dict:
        return rights_register()

    @router.get("/roster")
    def get_roster() -> dict:
        return {"items": model_roster()}

    @router.post("/matches/{match_id}/reports/assemble")
    def assemble_match_report(match_id: str, payload: dict | None = None) -> dict:
        del match_id
        body = payload or {}
        return assemble_report(
            metrics=list(body.get("metrics") or []),
            events=list(body.get("events") or []),
            claimed_evidence_ids=list(body.get("claimedEvidenceIds") or []),
            known_evidence_ids=set(body.get("knownEvidenceIds") or []),
            narrative=body.get("narrative"),
        )

    @router.post("/cost/estimate")
    def estimate_cost(payload: dict | None = None) -> dict:
        body = payload or {}
        return jsonable(
            match_cost(
                allocated_compute=float(body.get("allocatedCompute") or 0.0),
                retained_storage=float(body.get("retainedStorage") or 0.0),
                transfer=float(body.get("transfer") or 0.0),
                model_api=float(body.get("modelApi") or 0.0),
                retry_overhead=float(body.get("retryOverhead") or 0.0),
                review_labour=float(body.get("reviewLabour") or 0.0),
                fixed_share=float(body.get("fixedShare") or 0.0),
                export_fps=body.get("exportFps"),
            )
        )

    @router.post("/matches/{match_id}/incidents/package")
    def incident_package(match_id: str, payload: dict | None = None) -> dict:
        del match_id
        body = payload or {}
        return level0_incident_package(
            clips=list(body.get("clips") or []),
            notes=list(body.get("notes") or []),
            bookmarks=[float(item) for item in body.get("bookmarks") or []],
        )

    @router.get("/credits")
    def get_credits() -> dict:
        return credit_allocation()

    @router.get("/admission/{profile}")
    def get_admission(profile: str) -> dict:
        try:
            return jsonable(admit_camera(profile))  # type: ignore[arg-type]
        except KeyError as exc:
            raise HTTPException(status_code=400, detail="Unknown camera profile") from exc

    @router.post("/media/admit")
    def post_media_admit(body: MediaAdmitBody) -> dict:
        identity = SourceClockIdentity(
            sourceSha256=body.sourceSha256,
            byteSize=body.byteSize,
            codec=body.codec,
            audioTracks=body.audioTracks,
            decodeErrors=body.decodeErrors,
            variableFrameRate=body.variableFrameRate,
            rotation=body.rotation,
        )
        return admit_media(
            identity,
            existing_digests=set(body.existingDigests),
            require_audio=body.requireAudio,
        )

    @router.get("/xt")
    def get_xt() -> dict:
        return xt_deferred_plan()

    @router.post("/library/search")
    def post_library_search(body: LibrarySearchBody) -> dict:
        return search_match_library(query=body.query, matches=body.matches)

    @router.post("/matches/{match_id}/players")
    def post_players(match_id: str, body: PlayerBody) -> dict:
        del match_id
        return player_observations(body.rows, identity_continuous=body.identityContinuous)

    @router.get("/jobs/{request_id}/rates")
    def job_rates(request_id: str) -> dict:
        try:
            _job_ledger.receipt(request_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
        rates = FourRatesReceipt(
            decodeCount=0,
            detectorPrimaryCount=0,
            detectorRecoveryCount=0,
            trackerUpdateCount=0,
            exportCount=0,
            exportFpsEqualsInferenceFps=False,
            decodeFpsEqualsExportFps=False,
            notes=("EXPORT_FPS_IS_NOT_INFERENCE_FPS",),
        )
        return {
            "decodeCount": rates.decodeCount,
            "detectorPrimaryCount": rates.detectorPrimaryCount,
            "detectorRecoveryCount": rates.detectorRecoveryCount,
            "trackerUpdateCount": rates.trackerUpdateCount,
            "exportCount": rates.exportCount,
            "exportFpsEqualsInferenceFps": rates.exportFpsEqualsInferenceFps,
            "decodeFpsEqualsExportFps": rates.decodeFpsEqualsExportFps,
            "notes": list(rates.notes),
        }

    @router.post("/setup/assess")
    def post_setup_assess(payload: dict | None = None) -> dict:
        body = payload or {}
        return assess_match_setup(
            camera_profile=str(body.get("cameraProfile") or "stitched_panoramic_view"),
            pitch_length_m=body.get("pitchLengthM"),
            rights=dict(body.get("rights") or {}),
            periods=list(body.get("periods") or []),
        )

    @router.get("/metrics/inspect/{metric}")
    def get_metric_inspect(metric: str) -> dict:
        return inspect_metric(metric)

    @router.get("/residency")
    def get_residency() -> dict:
        return residency_claim(requested_region="eu", provider="daytona")

    @router.post("/matches")
    def post_match(payload: dict | None = None) -> dict:
        body = payload or {}
        return create_match(
            title=str(body.get("title") or "untitled"),
            camera_profile=str(body.get("cameraProfile") or "stitched_panoramic_view"),
            rights=dict(body.get("rights") or {}),
        )

    @router.get("/risks")
    def get_risks() -> dict:
        return {"items": risk_register()}

    @router.get("/milestones")
    def get_milestones() -> dict:
        return {
            "items": milestone_plan(),
            "owners": owners(),
            "progress": progress_signal(
                completed_analyst_tasks=0,
                validated_capability_gates=0,
                merged_files=0,
            ),
        }

    @router.get("/training/drills")
    def get_training_drills() -> dict:
        return drill_library()

    @router.get("/targets")
    def get_targets() -> dict:
        return metadata_api_targets()

    return router
