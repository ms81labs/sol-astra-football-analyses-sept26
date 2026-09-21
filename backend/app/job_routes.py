"""Job lifecycle and cost API routes."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, Header, HTTPException

from .jobs import JobRunner
from .schemas import MatchRecord
from .storage import Storage
from .workbench.access import object_access_decision
from .workbench.errors import ReconciliationRequired
from .workbench.jobs import attach_durable_job_view, cancellation_does_not_erase_charges


def create_job_router(
    storage: Storage,
    runner: JobRunner,
    require_match: Callable[..., MatchRecord],
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/jobs/{job_id}")
    def get_job(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_object_scope: str | None = Header(default=None),
        x_deployment_boundary: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ) -> dict:
        try:
            job = storage.get_job(job_id)
            match = storage.get_match(job.matchId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
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
        return attach_durable_job_view(job.model_dump(mode="json"), runner.ledger)
    
    @router.get("/api/matches/{match_id}/cost")
    def get_match_cost(match: MatchRecord = Depends(require_match)) -> dict:
        return {"matchId": match.id, **runner.ledger.cost_summary(match_id=match.id)}
    
    @router.get("/api/jobs/{job_id}/cost")
    def get_job_cost(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_object_scope: str | None = Header(default=None),
        x_deployment_boundary: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ) -> dict:
        try:
            job = storage.get_job(job_id)
            match = storage.get_match(job.matchId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
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
        return runner.ledger.cost_for(job_id)
    
    @router.get("/api/jobs/{job_id}/budget")
    def get_job_budget(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_object_scope: str | None = Header(default=None),
        x_deployment_boundary: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ) -> dict:
        try:
            job = storage.get_job(job_id)
            match = storage.get_match(job.matchId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
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
        cost = runner.ledger.cost_for(job_id)
        # Compatibility envelopes are views, not a second reservation or an invoice.
        from .workbench.money import admission_money, money
        actual = cost["actualTotal"]
        exceeded = "BUDGET_BREACH" in cost["reasonCodes"]
        reserved = {"authorised": False, "reserved": cost["reservedTotal"],
                    "estimate": cost["reservedTotal"], "currency": cost["currency"]}
        reconcile = {"reserved": cost["reservedTotal"], "actual": actual,
                     "variance": None if actual is None else float(money(actual) - money(cost["authorisedBudget"])),
                     "exceeded": exceeded, "alert": exceeded, "billingComplete": cost["billingComplete"]}
        return {"reserve": reserved, "reconcile": reconcile, "cost": cost}
    
    @router.get("/api/jobs/{job_id}/charges")
    def get_job_charges(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_object_scope: str | None = Header(default=None),
        x_deployment_boundary: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ) -> dict:
        try:
            job = storage.get_job(job_id)
            match = storage.get_match(job.matchId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
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
        view = attach_durable_job_view(job.model_dump(mode="json"), runner.ledger)
        cost = view["costSummary"]
        cancelled = bool(view.get("cancelRequested") or job.status == "cancelled")
        legacy = cancellation_does_not_erase_charges(cancelled=cancelled, incurred=cost["settledTotal"])
        return {**legacy, **cost, "costSummary": view["costSummary"],
                "reasonCodes": sorted(set(legacy["reasonCodes"]) | set(cost["reasonCodes"]))}
    
    @router.post("/api/jobs/{job_id}/cancel")
    def cancel_job(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_object_scope: str | None = Header(default=None),
        x_deployment_boundary: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ) -> dict:
        try:
            job = storage.get_job(job_id)
            match = storage.get_match(job.matchId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
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
        runner.ledger.request_cancel(job_id)
        return attach_durable_job_view(job.model_dump(mode="json"), runner.ledger)
    
    @router.post("/api/jobs/{job_id}/retry")
    def retry_job(
        job_id: str,
        payload: dict | None = None,
        authorization: str | None = Header(default=None),
        x_object_scope: str | None = Header(default=None),
        x_deployment_boundary: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ) -> dict:
        try:
            job = storage.get_job(job_id)
            match = storage.get_match(job.matchId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
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
        anchor = (payload or {}).get("retryOfAttemptId")
        if anchor is not None and (not isinstance(anchor, str) or not anchor or len(anchor) > 128):
            raise HTTPException(status_code=422, detail="invalid retryOfAttemptId")
        if runner.ledger.request(job_id).authorisedLocation != "local" and anchor is None:
            raise ReconciliationRequired("paid retry requires retryOfAttemptId from its receipt")
        before = runner.ledger.latest_attempt(job_id)
        attempt = runner.retry(job_id, retry_of_attempt_id=anchor)
        if attempt.attemptId != before.attemptId and attempt.status == "submitted":
            job = storage.reset_job_for_retry(job_id)
            runner.start(job_id)
        return attach_durable_job_view(job.model_dump(mode="json"), runner.ledger)
    
    @router.post("/api/jobs/{job_id}/timeout")
    def timeout_job(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_object_scope: str | None = Header(default=None),
        x_deployment_boundary: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ) -> dict:
        try:
            job = storage.get_job(job_id)
            match = storage.get_match(job.matchId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
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
        try:
            runner.ledger.timeout_before_response(job_id, owner_id=f"job:{job_id}")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
        return attach_durable_job_view(job.model_dump(mode="json"), runner.ledger)
    
    @router.post("/api/jobs/{job_id}/lost-connection")
    def lost_connection_job(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_object_scope: str | None = Header(default=None),
        x_deployment_boundary: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ) -> dict:
        try:
            job = storage.get_job(job_id)
            match = storage.get_match(job.matchId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
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
        try:
            runner.ledger.lost_connection(job_id, owner_id=f"job:{job_id}")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
        return attach_durable_job_view(job.model_dump(mode="json"), runner.ledger)
    
    @router.get("/api/jobs/{job_id}/rates")
    def get_job_rates(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_object_scope: str | None = Header(default=None),
        x_deployment_boundary: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ) -> dict:
        try:
            job = storage.get_job(job_id)
            match = storage.get_match(job.matchId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc
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
        return storage.four_rates_for_match(match.id)

    return router
