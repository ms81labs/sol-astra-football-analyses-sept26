"""HTTP surface for the v1.1 workbench."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .assistance import AssistancePolicy, AssistanceRouter, execute_typed_query, parse_typed_query
from .contracts import jsonable
from .dossier import build_baseline_dossier, build_release_dossier
from .evaluation import current_repository_evaluation_gate
from .evidence import EvidenceStore, metric_dictionary, summarize_legacy_match
from .flags import feature_flags
from .geometry import review_incident_geometry
from .jobs import DurableJobLedger, JobRequest
from .native import native_gate, probe_gpu
from .review import CorrectionLog, new_correction, playlist_export_interval
from .store import WorkbenchStore

_correction_log = CorrectionLog()
_job_ledger = DurableJobLedger()
_router_assistance = AssistanceRouter(providers_enabled=False)
_evidence_store = EvidenceStore()


class CorrectionBody(BaseModel):
    kind: str
    payload: dict = Field(default_factory=dict)
    author: str = "analyst"
    crashBeforeCommit: bool = False


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


_CORRECTION_INVALIDATION = {
    "team_mapping": "team_mapping",
    "track_split": "track_edit",
    "track_join": "track_edit",
    "event_reject": "team_mapping",
    "event_accept": "team_mapping",
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
        saved = _correction_log.submit(correction, crash_before_commit=body.crashBeforeCommit)
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

    return router
