"""GA-12 durable jobs, cost ledger, selective recomputation and cleanup."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from .cache import REBUILD_FOR, cache_identity
from .contracts import JobPhase, StrictModel

_RUNNING_STATUSES = {
    "validating",
    "waiting_for_capacity",
    "running",
    "importing",
    "cancelling",
}

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
    pixelFormat: str = "bgr24"
    precision: str = "fp32"
    namespace: Literal["development", "production", "validation", "held_out_evaluation"] = "development"
    cameraProfile: str = "stitched_panoramic_view"


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
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else None
        self.requests: dict[str, JobRequest] = {}
        self.attempts: dict[str, list[JobAttempt]] = {}
        self.costs: list[CostEntry] = []
        self.cancel_flags: set[str] = set()
        if self.db_path is not None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._ensure_schema()
            self._load()
            self.reconcile_after_restart()

    def _open_connection(self) -> sqlite3.Connection:
        assert self.db_path is not None
        connection = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = self._open_connection()
        try:
            yield connection
            connection.commit()
        except BaseException:
            try:
                connection.rollback()
            except Exception:
                pass
            raise
        finally:
            connection.close()

    def close(self) -> None:
        if self.db_path is None:
            return
        try:
            connection = self._open_connection()
            try:
                connection.execute("PRAGMA wal_checkpoint(PASSIVE)")
            finally:
                connection.close()
        except Exception:
            return

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS job_ledger_requests (
                    request_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS job_ledger_attempts (
                    attempt_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS job_ledger_costs (
                    attempt_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS job_ledger_cancels (
                    request_id TEXT PRIMARY KEY
                );
                """
            )

    def _load(self) -> None:
        with self._connect() as connection:
            for row in connection.execute("SELECT request_id, payload_json FROM job_ledger_requests"):
                self.requests[row["request_id"]] = JobRequest.model_validate_json(row["payload_json"])
            for row in connection.execute(
                "SELECT request_id, payload_json FROM job_ledger_attempts ORDER BY request_id, sequence"
            ):
                self.attempts.setdefault(row["request_id"], []).append(JobAttempt.model_validate_json(row["payload_json"]))
            for row in connection.execute("SELECT payload_json FROM job_ledger_costs"):
                self.costs.append(CostEntry.model_validate_json(row["payload_json"]))
            self.cancel_flags = {row["request_id"] for row in connection.execute("SELECT request_id FROM job_ledger_cancels")}

    def _persist(self) -> None:
        if self.db_path is None:
            return
        with self._connect() as connection:
            for request_id, request in self.requests.items():
                connection.execute(
                    "INSERT OR REPLACE INTO job_ledger_requests (request_id, payload_json) VALUES (?, ?)",
                    (request_id, request.model_dump_json()),
                )
            for request_id, attempts in self.attempts.items():
                for sequence, attempt in enumerate(attempts):
                    connection.execute(
                        "INSERT OR REPLACE INTO job_ledger_attempts (attempt_id, request_id, sequence, payload_json) VALUES (?, ?, ?, ?)",
                        (attempt.attemptId, request_id, sequence, attempt.model_dump_json()),
                    )
            for entry in self.costs:
                connection.execute(
                    "INSERT OR REPLACE INTO job_ledger_costs (attempt_id, request_id, payload_json) VALUES (?, ?, ?)",
                    (entry.attemptId, entry.requestId, entry.model_dump_json()),
                )
            for request_id in self.cancel_flags:
                connection.execute(
                    "INSERT OR IGNORE INTO job_ledger_cancels (request_id) VALUES (?)",
                    (request_id,),
                )

    def reconcile_after_restart(self) -> None:
        for request_id, attempts in list(self.attempts.items()):
            if not attempts:
                continue
            if attempts[-1].status in _RUNNING_STATUSES:
                self.timeout_before_response(request_id)

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
        self._persist()
        return attempt

    def transition(self, request_id: str, status: JobStatus, **updates: Any) -> JobAttempt:
        attempt = self.attempts[request_id][-1]
        if request_id in self.cancel_flags and status not in {"cancelled", "cancelling", "outcome_unknown"}:
            status = "cancelling"
        updated = attempt.model_copy(update={"status": status, **updates})
        self.attempts[request_id][-1] = updated
        self._persist()
        return updated

    def timeout_before_response(self, request_id: str) -> JobAttempt:
        return self.transition(request_id, "outcome_unknown", error="timeout_before_response", cleanupResult="unknown")

    def lost_connection(self, request_id: str) -> JobAttempt:
        return self.transition(request_id, "outcome_unknown", error="lost_connection", cleanupResult="unknown")

    def cancel(self, request_id: str) -> JobAttempt:
        self.cancel_flags.add(request_id)
        self._persist()
        return self.transition(request_id, "cancelling")

    def request_cancel(self, request_id: str) -> JobAttempt | None:
        self.cancel_flags.add(request_id)
        self._persist()
        if request_id not in self.attempts:
            return None
        latest = self.attempts[request_id][-1]
        if latest.status in {"complete", "failed", "cancelled", "outcome_unknown"}:
            return latest
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
        self._persist()
        return attempt

    def invalidate_for(self, change: Literal["report", "team_mapping", "track_edit", "calibration", "perception", "ownership"]) -> list[str]:
        return list(REBUILD_FOR[change])

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
            cacheIdentity=cache_identity(
                source_sha256=request.sourceSha256,
                interval_start=request.intervalStart,
                interval_end=request.intervalEnd,
                decoder_version=request.decoderVersion,
                model_hash=request.modelHash,
                temporal_policy=request.temporalPolicy,
                output_schema=request.outputSchema,
                namespace=request.namespace,
            ),
            error=attempt.error,
        )

    def cancel_requested(self, request_id: str) -> bool:
        return request_id in self.cancel_flags

    def terminated(self, request_id: str) -> bool:
        status = self.attempts[request_id][-1].status
        return status in {"cancelled", "complete", "failed"}

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

    def cost_summary(self) -> dict[str, float | int]:
        reserved = [entry.reserved for entry in self.costs]
        actual = [entry.actual for entry in self.costs if entry.actual is not None]
        return {
            "attempts": len(self.costs),
            "reservedTotal": round(sum(reserved), 4) if reserved else 0.0,
            "actualTotal": round(sum(actual), 4) if actual else 0.0,
            "p50Reserved": _percentile(reserved, 50),
            "p95Reserved": _percentile(reserved, 95),
        }

    def cost_for(self, request_id: str) -> dict[str, float | int | str]:
        entries = [entry for entry in self.costs if entry.requestId == request_id]
        reserved = [entry.reserved for entry in entries]
        actual = [entry.actual for entry in entries if entry.actual is not None]
        return {
            "requestId": request_id,
            "attempts": len(entries),
            "reservedTotal": round(sum(reserved), 4) if reserved else 0.0,
            "actualTotal": round(sum(actual), 4) if actual else 0.0,
            "p50Reserved": _percentile(reserved, 50),
            "p95Reserved": _percentile(reserved, 95),
        }


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((percentile / 100) * (len(ordered) - 1)))))
    return float(ordered[index])


def worker_environment(request: JobRequest, *, host_secret: str) -> dict[str, str]:
    del host_secret
    return {
        "REQUEST_ID": request.requestId,
        "NAMESPACE": request.namespace,
        "AUTHORISED_LOCATION": request.authorisedLocation,
        "PIXEL_FORMAT": request.pixelFormat,
        "PRECISION": request.precision,
    }


def cleanup_failure_is_complete(cleanup_result: str) -> bool:
    return cleanup_result == "confirmed"


def pause_experiment(*, remaining: float, termination_and_recovery: float) -> bool:
    return remaining < termination_and_recovery


def deployment_mode(name: str) -> dict[str, object]:
    modes = {
        "local_only": {"admitted": True, "silentCloudFallback": False, "requiresGNetwork": False},
        "local_app_plus_burst_gpu": {"admitted": False, "silentCloudFallback": False, "requiresGNetwork": False, "requiresAuthorisedBudget": True},
        "hosted_collaboration": {"admitted": False, "silentCloudFallback": False, "requiresGNetwork": True},
    }
    return modes[name]


def distributed_broker(*, measured_workload_needs: bool = False) -> dict[str, object]:
    del measured_workload_needs
    return {
        "enabled": False,
        "admitted": False,
        "renamesCurrentQueue": False,
    }


def vector_database(*, measured_recall_benefit: bool = False) -> dict[str, object]:
    del measured_recall_benefit
    return {
        "enabled": False,
        "admitted": False,
        "embeddingsProveTacticalWeakness": False,
    }


def attach_durable_job_view(payload: dict[str, Any], ledger: DurableJobLedger) -> dict[str, Any]:
    job_id = str(payload.get("id") or payload.get("jobId") or "")
    view = dict(payload)
    storage_terminal = view.get("status") in {"completed", "complete", "failed", "cancelled"}
    view["cancelRequested"] = ledger.cancel_requested(job_id)
    if job_id in ledger.attempts:
        receipt = ledger.receipt(job_id)
        view["durablePhase"] = receipt.status
        view["ledgerStatus"] = receipt.status
        view["attemptId"] = receipt.attemptId
        view["costReserved"] = receipt.costReserved
        view["costActual"] = receipt.costActual
        view["cleanupResult"] = receipt.cleanupResult
        view["temporalPolicy"] = receipt.temporalPolicy
        view["cacheIdentity"] = receipt.cacheIdentity
        view["terminated"] = storage_terminal or ledger.terminated(job_id) or receipt.status in {"complete", "failed"}
    else:
        view["durablePhase"] = None
        view["ledgerStatus"] = None
        view["cleanupResult"] = "unknown"
        view["terminated"] = storage_terminal
        view["costReserved"] = view.get("costReserved", 0.0)
    return view


def signed_scoped_job_access(*, token: str | None, job_id: str, token_job_id: str | None) -> dict[str, object]:
    del token, job_id, token_job_id
    return {
        "admitted": False,
        "scoped": False,
        "hmacOrJwtImplemented": False,
        "reasonCodes": ["HOSTED_SIGNED_ACCESS_UNIMPLEMENTED", "UNSIGNED_OR_UNSCOPED_JOB_ACCESS"],
    }


def egress_policy(*, destination: str, authorised_hosts: frozenset[str]) -> dict[str, object]:
    from urllib.parse import urlparse

    host = (urlparse(destination).hostname or "").lower()
    admitted = bool(host) and host in authorised_hosts
    return {
        "admitted": admitted,
        "defaultDeny": True,
        "reasonCodes": [] if admitted else ["WORKER_EGRESS_DENIED"],
    }


def cancellation_does_not_erase_charges(*, cancelled: bool, incurred: float) -> dict[str, object]:
    return {
        "cancelled": cancelled,
        "incurred": incurred,
        "chargesErased": False,
        "reasonCodes": ["CANCELLATION_DOES_NOT_ERASE_INCURRED_CHARGES"] if cancelled else [],
    }
