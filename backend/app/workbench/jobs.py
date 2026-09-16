"""GA-12 durable jobs, cost ledger, selective recomputation and cleanup."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import Field

from .contracts import JobPhase, StrictModel

MAX_ATTEMPTS = 3

JobStatus = Literal[
    "submitted",
    "validating",
    "waiting_for_capacity",
    "running",
    "importing",
    "complete",
    "failed",
    "cancelling",
    "cancelled",
    "outcome_unknown",
]


class JobRequest(StrictModel):
    requestId: str
    matchId: str
    sourceSha256: str
    intervalStart: float
    intervalEnd: float
    temporalPolicy: str
    decoderVersion: str
    modelHash: str
    outputSchema: str
    budget: float
    authorisedLocation: Literal["local", "daytona"]
    fallbackPolicy: str = "cpu_local"


class JobAttempt(StrictModel):
    attemptId: str
    requestId: str
    status: JobStatus
    selectedBackend: str | None = None
    actualHardware: str | None = None
    reservedCost: float = 0.0
    actualCost: float | None = None
    cleanupResult: Literal["confirmed", "failed", "not_required", "unknown"] = "not_required"
    error: str | None = None


class CostEntry(StrictModel):
    requestId: str
    attemptId: str
    reserved: float
    actual: float | None
    scope: str


class DurableJobLedger:
    def __init__(self) -> None:
        self.requests: dict[str, JobRequest] = {}
        self.attempts: dict[str, list[JobAttempt]] = {}
        self.costs: list[CostEntry] = []
        self.cancel_flags: set[str] = set()

    def submit(self, request: JobRequest) -> JobAttempt:
        existing = self.requests.get(request.requestId)
        if existing is not None:
            if existing != request:
                raise ValueError("idempotent request payload mismatch")
            latest = self.attempts[request.requestId][-1]
            if latest.status not in {"failed", "cancelled", "outcome_unknown"}:
                return latest
        self.requests[request.requestId] = request
        attempt = JobAttempt(
            attemptId=str(uuid.uuid4()),
            requestId=request.requestId,
            status="submitted",
            reservedCost=request.budget,
        )
        self.attempts.setdefault(request.requestId, []).append(attempt)
        self.costs.append(
            CostEntry(requestId=request.requestId, attemptId=attempt.attemptId, reserved=request.budget, actual=None, scope="job")
        )
        return attempt

    def transition(self, request_id: str, status: JobStatus, **updates: Any) -> JobAttempt:
        attempt = self.attempts[request_id][-1]
        if request_id in self.cancel_flags and status not in {"cancelled", "cancelling", "outcome_unknown"}:
            status = "cancelling"
        updated = attempt.model_copy(update={"status": status, **updates})
        self.attempts[request_id][-1] = updated
        return updated

    def timeout_before_response(self, request_id: str) -> JobAttempt:
        return self.transition(request_id, "outcome_unknown", error="timeout_before_response", cleanupResult="unknown")

    def lost_connection(self, request_id: str) -> JobAttempt:
        return self.transition(request_id, "outcome_unknown", error="lost_connection", cleanupResult="unknown")

    def cancel(self, request_id: str) -> JobAttempt:
        self.cancel_flags.add(request_id)
        return self.transition(request_id, "cancelling")

    def confirm_cleanup(self, request_id: str, *, ok: bool) -> JobAttempt:
        return self.transition(
            request_id,
            self.attempts[request_id][-1].status,
            cleanupResult="confirmed" if ok else "failed",
        )

    def retry(self, request_id: str) -> JobAttempt:
        latest = self.attempts[request_id][-1]
        if latest.status not in {"failed", "cancelled"}:
            if latest.status == "outcome_unknown":
                raise RuntimeError("reconcile remote state before retrying an outcome-unknown job")
            return latest
        if len(self.attempts[request_id]) >= MAX_ATTEMPTS:
            raise RuntimeError("retry budget exhausted")
        request = self.requests[request_id]
        attempt = JobAttempt(
            attemptId=str(uuid.uuid4()),
            requestId=request_id,
            status="submitted",
            reservedCost=request.budget,
        )
        self.attempts[request_id].append(attempt)
        return attempt

    def invalidate_for(self, change: Literal["report", "team_mapping", "track_edit", "calibration", "perception"]) -> list[str]:
        rebuild = {
            "report": ["report"],
            "team_mapping": ["team_state", "events", "metrics", "report"],
            "track_edit": ["ownership", "player_events", "metrics", "report"],
            "calibration": ["pitch_positions", "physical_metrics", "tactical_metrics", "report"],
            "perception": ["observations", "tracking", "dependants"],
        }[change]
        return rebuild

    def receipt(self, request_id: str) -> JobPhase:
        attempt = self.attempts[request_id][-1]
        request = self.requests[request_id]
        return JobPhase(
            requestId=request_id,
            attemptId=attempt.attemptId,
            status=attempt.status,
            selectedBackend=attempt.selectedBackend,
            actualHardware=attempt.actualHardware,
            temporalPolicy=request.temporalPolicy,
            fallbackPolicy=request.fallbackPolicy,
            costReserved=attempt.reservedCost,
            costActual=attempt.actualCost,
            cleanupResult=attempt.cleanupResult,
        )

    def import_attempt(
        self,
        request_id: str,
        *,
        sha256: str,
        expected_sha256: str,
        schema_ok: bool,
        complete: bool,
    ) -> JobAttempt:
        if not schema_ok or not complete or sha256 != expected_sha256:
            return self.transition(request_id, "failed", error="quarantined_partial_or_corrupt")
        return self.transition(request_id, "complete")

    def disk_exhaustion(self, request_id: str) -> JobAttempt:
        return self.transition(request_id, "failed", error="disk_exhaustion")
