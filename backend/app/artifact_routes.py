"""Match event, artifact export, and report retrieval routes."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response

from .export_flatteners import (
    EVENT_CSV_FIELDS,
    FRAME_CSV_FIELDS,
    METRIC_CSV_FIELDS,
    flatten_events_for_csv,
    flatten_frames_for_csv,
    flatten_metrics_for_csv,
    render_csv,
)
from .report_export import build_match_report_export
from .report_store import ReportStore
from .schemas import MatchEventsResponse, MatchRecord
from .storage import Storage


def create_artifact_router(
    storage: Storage,
    require_match: Callable[..., MatchRecord],
    bundle_builder: Callable[..., dict[str, object]],
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/matches/{match_id}/events")
    def get_events(
        match: MatchRecord = Depends(require_match),
        generationId: str | None = None,
    ) -> dict:
        try:
            with storage.generation_snapshot(match.id, generation_id=generationId) as ref:
                response = MatchEventsResponse(matchId=match.id, events=storage.load_events(match.id))
                return {**response.model_dump(mode="json"), "generationId": ref.generationId}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Events not ready") from exc

    def snapshot_csv(match: MatchRecord, generation_id: str | None, kind: str) -> Response:
        try:
            with storage.generation_snapshot(match.id, generation_id=generation_id) as ref:
                if kind == "frames":
                    rows, fields = flatten_frames_for_csv(storage.load_frames(match.id)), FRAME_CSV_FIELDS
                elif kind == "events":
                    rows, fields = flatten_events_for_csv(storage.load_events(match.id)), EVENT_CSV_FIELDS
                else:
                    summary, _, _, _ = storage.load_analytics(match.id)
                    rows, fields = flatten_metrics_for_csv(summary.metricAvailability), METRIC_CSV_FIELDS
                csv_payload = render_csv(rows, fields)
                return Response(
                    content=csv_payload,
                    media_type="text/csv",
                    headers={
                        "Content-Disposition": f'attachment; filename="{match.id}-{kind}.csv"',
                        "X-Generation-Id": ref.generationId,
                    },
                )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Match artifacts not ready") from exc

    @router.get("/api/matches/{match_id}/export/frames.csv")
    def export_frames_csv(
        match: MatchRecord = Depends(require_match),
        generationId: str | None = None,
    ) -> Response:
        return snapshot_csv(match, generationId, "frames")

    @router.get("/api/matches/{match_id}/export/events.csv")
    def export_events_csv(
        match: MatchRecord = Depends(require_match),
        generationId: str | None = None,
    ) -> Response:
        return snapshot_csv(match, generationId, "events")

    @router.get("/api/matches/{match_id}/export/metrics.csv")
    def export_metrics_csv(
        match: MatchRecord = Depends(require_match),
        generationId: str | None = None,
    ) -> Response:
        return snapshot_csv(match, generationId, "metrics")

    @router.get("/api/matches/{match_id}/export/match.json")
    def export_match_json(
        match: MatchRecord = Depends(require_match),
        generationId: str | None = None,
    ) -> dict:
        try:
            return bundle_builder(storage, match.id, generation_id=generationId)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Match artifacts not ready") from exc

    @router.get("/api/matches/{match_id}/reports")
    def get_generation_reports(
        match: MatchRecord = Depends(require_match),
        generationId: str | None = None,
    ) -> dict:
        try:
            return ReportStore(storage).view(match.id, generation_id=generationId)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Reports not ready") from exc

    @router.get("/api/matches/{match_id}/reports/legacy/{task_type}")
    def get_legacy_report(
        task_type: str,
        match: MatchRecord = Depends(require_match),
    ) -> dict:
        try:
            return ReportStore(storage).legacy(match.id, task_type)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Legacy report unavailable") from exc

    @router.get("/api/matches/{match_id}/report/html")
    def get_match_report_html(
        match: MatchRecord = Depends(require_match),
        generationId: str | None = None,
    ) -> HTMLResponse:
        try:
            with storage.generation_snapshot(match.id, generation_id=generationId) as generation:
                summary, _, formation_timeline, shots = storage.load_analytics(match.id)
                events = storage.load_events(match.id)
                view = ReportStore(storage).view(match.id, generation_id=generation.generationId)
                reports = view["reports"]
                html = build_match_report_export(
                    match=storage.get_match(match.id),
                    summary=summary,
                    formation_timeline=formation_timeline,
                    shots=shots,
                    events=events,
                    tactical_report=reports.get("tactical_report", {}).get("payload"),
                    drills=reports.get("drills", {}).get("payload"),
                    report_context=view,
                )
                return HTMLResponse(
                    content=html,
                    headers={"X-Generation-Id": generation.generationId},
                )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Analytics not ready") from exc

    return router
