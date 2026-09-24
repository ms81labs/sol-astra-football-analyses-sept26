"""GA-12 durable jobs, cost ledger, selective recomputation and cleanup."""

from __future__ import annotations

import logging

import hashlib
import json
import sqlite3
import tempfile
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator

from .money import ZERO, admission_money, money, text, total
from .billing import AttemptBilling, CostSummary

from .errors import (
    BudgetExhausted,
    IdempotencyConflict,
    NotOwner,
    ReconciliationRequired,
    RetryBudgetExhausted,
    StaleTransition,
)

from .cache import REBUILD_FOR, cache_identity
from .contracts import JobPhase, StrictModel


LOGGER = logging.getLogger(__name__)

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
    budget: float = Field(ge=0, allow_inf_nan=False)
    authorisedLocation: Literal["local", "daytona", "cloud"]
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    scope: Literal["job", "provider"] = "job"
    providerTask: str | None = None
    executionBound: dict[str, Any] | None = None

    @field_validator("budget", mode="before")
    @classmethod
    def exact_budget(cls, value):
        admission_money(value)
        return value
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
    actualCost: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    cleanupResult: Literal["confirmed", "failed", "not_required", "unknown"] = "not_required"
    error: str | None = None
    sequence: int = 1
    ownerId: str | None = None
    leaseExpiresAt: float | None = None
    revision: int = 0
    reconciled: bool = False
    # None means legacy dispatch provenance was not established.
    dispatchStarted: bool | None = None


class CostEntry(StrictModel):
    requestId: str
    attemptId: str
    reserved: float
    actual: float | None
    scope: str


@contextmanager
def maintain_job_lease(
    ledger: "DurableJobLedger",
    request_id: str,
    *,
    owner_id: str,
    lease_seconds: float = 60.0,
) -> Iterator[None]:
    """Renew a worker lease independently of provider progress callbacks."""
    stopped = threading.Event()

    def renew() -> None:
        interval = max(0.1, lease_seconds / 3)
        while not stopped.wait(interval):
            try:
                attempt = ledger.latest_attempt(request_id)
                if attempt.status not in _RUNNING_STATUSES | {"submitted"}:
                    return
                ledger.heartbeat(
                    attempt.attemptId,
                    owner_id=owner_id,
                    lease_seconds=lease_seconds,
                )
            except (KeyError, NotOwner):
                return

    attempt = ledger.latest_attempt(request_id)
    ledger.heartbeat(attempt.attemptId, owner_id=owner_id, lease_seconds=lease_seconds)
    thread = threading.Thread(target=renew, name=f"job-lease-{request_id}", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=1.0)


class DurableJobLedger:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self._temporary_directory = None
        if db_path is None:
            self._temporary_directory = tempfile.TemporaryDirectory(prefix="ga-job-ledger-")
            db_path = Path(self._temporary_directory.name) / "ledger.sqlite3"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()
        with self._transaction() as connection:
            if "amount_exact" not in {r["name"] for r in connection.execute("PRAGMA table_info(job_charges)")}:
                connection.execute("ALTER TABLE job_charges ADD COLUMN amount_exact TEXT")
        self._migrate_legacy_once()
        self._migrate_billing_evidence()

    def _open_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA foreign_keys=ON")
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
                LOGGER.warning("job ledger transaction rollback failed")
            raise
        finally:
            connection.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._open_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def close(self) -> None:
        try:
            connection = self._open_connection()
            try:
                connection.execute("PRAGMA wal_checkpoint(PASSIVE)")
            finally:
                connection.close()
        except Exception:
            return
        if self._temporary_directory is not None:
            self._temporary_directory.cleanup()
            self._temporary_directory = None

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS job_requests (
                    request_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    authorised_budget REAL NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS job_attempts (
                    attempt_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL REFERENCES job_requests(request_id),
                    sequence INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    owner_id TEXT,
                    lease_expires_at REAL,
                    revision INTEGER NOT NULL DEFAULT 0,
                    reconciled INTEGER NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(request_id, sequence)
                );
                CREATE TABLE IF NOT EXISTS job_charges (
                    charge_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL REFERENCES job_requests(request_id),
                    attempt_id TEXT NOT NULL REFERENCES job_attempts(attempt_id),
                    kind TEXT NOT NULL CHECK(kind IN ('reserved','estimated','unsettled','settled','released')),
                    amount REAL,
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS job_billing_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    request_id TEXT NOT NULL REFERENCES job_requests(request_id),
                    attempt_id TEXT NOT NULL REFERENCES job_attempts(attempt_id),
                    state TEXT NOT NULL CHECK(state IN ('final','partial','unknown')),
                    total_exact TEXT,
                    reason TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS billing_by_attempt ON job_billing_events(attempt_id, sequence);
                CREATE INDEX IF NOT EXISTS charges_by_request ON job_charges(request_id, attempt_id);
                CREATE TABLE IF NOT EXISTS job_billing_migrations (
                    key TEXT PRIMARY KEY, receipt_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS job_charge_receipts (
                receipt_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS provider_results (
                    request_id TEXT PRIMARY KEY REFERENCES job_requests(request_id),
                    response_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS job_cancels (
                    request_id TEXT PRIMARY KEY REFERENCES job_requests(request_id),
                    requested_at TEXT NOT NULL,
                    termination_confirmed_at TEXT,
                    cleanup_confirmed_at TEXT,
                    cleanup_result TEXT
                );
                """
            )

    def _migrate_billing_evidence(self) -> None:
        """One startup migration. Preserve old payloads/charges; never infer zero."""
        with self._transaction() as connection:
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(job_charges)")}
            if "amount_exact" not in columns:
                connection.execute("ALTER TABLE job_charges ADD COLUMN amount_exact TEXT")
            if connection.execute("SELECT 1 FROM job_billing_migrations WHERE key='billing-v2'").fetchone():
                return
            count = 0
            for row in connection.execute("SELECT * FROM job_attempts"):
                attempt = self._attempt_from_row(row)
                if connection.execute("SELECT 1 FROM job_billing_events WHERE attempt_id=?", (attempt.attemptId,)).fetchone():
                    continue
                request = JobRequest.model_validate_json(connection.execute(
                    "SELECT payload_json FROM job_requests WHERE request_id=?", (attempt.requestId,)
                ).fetchone()["payload_json"])
                # Old remote reconciliation coerced an absent invoice to zero. Such
                # zero payloads cannot prove a no-charge outcome, even if reconciled.
                # Positive recorded actuals keep the historical invoice contract;
                # explicitly local execution remains positively non-billable.
                final = (attempt.actualCost is not None
                         and (money(attempt.actualCost) > ZERO or request.authorisedLocation == "local")
                         and attempt.status in {"complete", "failed", "cancelled"}
                         and money(attempt.actualCost) == self._attempt_charge_total(connection, attempt.attemptId, "settled"))
                self._billing_event(connection, attempt,
                    state="final" if final else "unknown",
                    amount=None if not final else money(attempt.actualCost),
                    event_id="migration-v2:" + attempt.attemptId,
                    reason="LEGACY_EXPLICIT_FINAL_INVOICE" if final else "LEGACY_BILLING_UNVERIFIED")
                count += 1
            connection.execute("INSERT INTO job_billing_migrations VALUES ('billing-v2', ?)",
                (json.dumps({"schemaVersion": 2, "attempts": count, "originalRowsPreserved": True}),))

    def _migrate_legacy_once(self) -> None:
        with self._transaction() as connection:
            if connection.execute("SELECT 1 FROM job_requests LIMIT 1").fetchone() is not None:
                return
            tables = {
                row["name"]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            if "job_ledger_requests" not in tables:
                return
            now = _now()
            for row in connection.execute("SELECT request_id, payload_json FROM job_ledger_requests"):
                request = JobRequest.model_validate_json(row["payload_json"])
                payload = _canonical_request_json(request)
                connection.execute(
                    "INSERT INTO job_requests VALUES (?, ?, ?, ?, 0, ?)",
                    (request.requestId, payload, _payload_sha256(payload), request.budget, now),
                )
            if "job_ledger_attempts" in tables:
                for row in connection.execute(
                    "SELECT request_id, sequence, payload_json FROM job_ledger_attempts ORDER BY request_id, sequence"
                ):
                    legacy = JobAttempt.model_validate_json(row["payload_json"])
                    attempt = legacy.model_copy(
                        update={"sequence": int(row["sequence"]) + 1, "ownerId": "legacy"}
                    )
                    self._insert_attempt(connection, attempt, now)
            if "job_ledger_costs" in tables:
                for row in connection.execute("SELECT payload_json FROM job_ledger_costs"):
                    entry = CostEntry.model_validate_json(row["payload_json"])
                    self._insert_charge(
                        connection,
                        entry.requestId,
                        entry.attemptId,
                        "reserved",
                        entry.reserved,
                    )
                    if entry.actual is not None:
                        self._insert_charge(
                            connection,
                            entry.requestId,
                            entry.attemptId,
                            "settled",
                            entry.actual,
                        )
                        if entry.reserved > entry.actual:
                            self._insert_charge(
                                connection,
                                entry.requestId,
                                entry.attemptId,
                                "released",
                                entry.reserved - entry.actual,
                            )
                    else:
                        attempt_row = connection.execute(
                            "SELECT status FROM job_attempts WHERE attempt_id=?",
                            (entry.attemptId,),
                        ).fetchone()
                        if attempt_row is not None and attempt_row["status"] == "outcome_unknown":
                            self._insert_charge(
                                connection,
                                entry.requestId,
                                entry.attemptId,
                                "unsettled",
                                entry.reserved,
                            )
                        elif attempt_row is not None and attempt_row["status"] in {
                            "complete",
                            "failed",
                            "cancelled",
                        }:
                            self._insert_charge(
                                connection,
                                entry.requestId,
                                entry.attemptId,
                                "released",
                                entry.reserved,
                            )
            if "job_ledger_cancels" in tables:
                for row in connection.execute("SELECT request_id FROM job_ledger_cancels"):
                    connection.execute(
                        "INSERT OR IGNORE INTO job_cancels (request_id, requested_at) VALUES (?, ?)",
                        (row["request_id"], now),
                    )

    @property
    def requests(self) -> dict[str, JobRequest]:
        with self._connect() as connection:
            return {
                row["request_id"]: JobRequest.model_validate_json(row["payload_json"])
                for row in connection.execute("SELECT request_id, payload_json FROM job_requests")
            }

    @property
    def attempts(self) -> dict[str, list[JobAttempt]]:
        result: dict[str, list[JobAttempt]] = {}
        with self._connect() as connection:
            connection.execute("BEGIN")
            for row in connection.execute(
                "SELECT request_id, payload_json FROM job_attempts ORDER BY request_id, sequence"
            ):
                result.setdefault(row["request_id"], []).append(self._attempt_view(connection, row))
        return result

    @property
    def costs(self) -> list[CostEntry]:
        with self._connect() as connection:
            connection.execute("BEGIN")
            result = []
            for row in connection.execute("SELECT * FROM job_attempts ORDER BY request_id, sequence"):
                attempt = self._attempt_from_row(row)
                state = self._billing_state(connection, attempt)
                result.append(CostEntry(requestId=attempt.requestId, attemptId=attempt.attemptId,
                    reserved=float(state.outstanding + state.unsettled),
                    actual=float(state.settled) if state.complete else None, scope="job"))
            return result


    @property
    def cancel_flags(self) -> set[str]:
        with self._connect() as connection:
            return {row["request_id"] for row in connection.execute("SELECT request_id FROM job_cancels")}

    def has_request(self, request_id: str) -> bool:
        with self._connect() as connection:
            return connection.execute(
                "SELECT 1 FROM job_requests WHERE request_id=?", (request_id,)
            ).fetchone() is not None

    def request(self, request_id: str) -> JobRequest:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM job_requests WHERE request_id=?", (request_id,)
            ).fetchone()
        if row is None:
            raise KeyError(request_id)
        return JobRequest.model_validate_json(row["payload_json"])

    def latest_attempt(self, request_id: str) -> JobAttempt:
        with self._connect() as connection:
            connection.execute("BEGIN")
            row = self._latest_attempt_row(connection, request_id)
            if row is None:
                raise KeyError(request_id)
            return self._attempt_view(connection, row)

    def admit(
        self,
        request: JobRequest,
        *,
        mode: Literal["submit", "retry"],
        owner_id: str,
        lease_seconds: float,
        reservation: float | None = None,
        group_limit: float | None = None,
        retry_of_attempt_id: str | None = None,
    ) -> JobAttempt:
        payload = _canonical_request_json(request)
        payload_sha = _payload_sha256(payload)
        now_epoch = time.time()
        now = _now()
        with self._transaction() as connection:
            request_row = connection.execute(
                "SELECT * FROM job_requests WHERE request_id=?", (request.requestId,)
            ).fetchone()
            if request_row is None:
                if mode == "retry":
                    raise ReconciliationRequired("retry requires an existing logical request")
                connection.execute(
                    "INSERT INTO job_requests VALUES (?, ?, ?, ?, 0, ?)",
                    (request.requestId, payload, payload_sha, request.budget, now),
                )
                latest = None
                sequence = 1
            else:
                if _canonical_request_json(JobRequest.model_validate_json(request_row["payload_json"])) != payload:
                    raise IdempotencyConflict(request.requestId)
                latest_row = self._latest_attempt_row(connection, request.requestId)
                latest = None if latest_row is None else self._attempt_from_row(latest_row)
                sequence = 1 if latest is None else latest.sequence + 1
                if retry_of_attempt_id is not None:
                    if mode != "retry":
                        raise ReconciliationRequired("retry anchor requires explicit retry mode")
                    anchor_row = connection.execute(
                        "SELECT * FROM job_attempts WHERE attempt_id=? AND request_id=?",
                        (retry_of_attempt_id, request.requestId),
                    ).fetchone()
                    if anchor_row is None:
                        raise ReconciliationRequired("retry anchor does not belong to this request")
                    anchor = self._attempt_from_row(anchor_row)
                    if latest is not None and latest.sequence > anchor.sequence:
                        # The same retry request always means the same immediate child,
                        # including when that child failed or became uncertain later.
                        child = connection.execute(
                            "SELECT * FROM job_attempts WHERE request_id=? AND sequence=?",
                            (request.requestId, anchor.sequence + 1),
                        ).fetchone()
                        return self._attempt_view(connection, child)
                if latest is not None:
                    if latest.status == "outcome_unknown" and not latest.reconciled:
                        raise ReconciliationRequired("reconcile outcome-unknown attempt before retry")
                    if latest.status in _RUNNING_STATUSES | {"submitted", "complete"}:
                        return latest
                    if mode == "submit":
                        return latest
                    connection.execute(
                        "DELETE FROM job_cancels WHERE request_id=?",
                        (request.requestId,),
                    )
            if sequence > MAX_ATTEMPTS:
                raise RetryBudgetExhausted("retry budget exhausted")
            existing_cost = self._cost_view(connection, request.requestId)
            if "BUDGET_BREACH" in existing_cost.reasonCodes:
                raise BudgetExhausted("observed invoice exceeded the authorised budget or reservation")
            if existing_cost.unsettledAttemptCount:
                raise ReconciliationRequired("billing reconciliation required before another attempt")
            settled, reserved, unsettled = self._budget_totals(connection, request.requestId)
            remaining = max(ZERO, money(request.budget) - settled - reserved - unsettled)
            reservation = admission_money(remaining if reservation is None else reservation)
            if reservation > remaining or (request.budget > 0 and reservation <= ZERO):
                raise BudgetExhausted("authorised budget exhausted")
            if request.authorisedLocation != "local":
                # An observed overrun must not be escaped by choosing a new request ID.
                # Free local work and existing idempotent receipts remain usable.
                for item in connection.execute("SELECT request_id, payload_json FROM job_requests"):
                    other = JobRequest.model_validate_json(item["payload_json"])
                    if other.currency == request.currency and "BUDGET_BREACH" in self._cost_view(connection, other.requestId).reasonCodes:
                        raise BudgetExhausted("billing reconciliation required after an observed budget breach")
            if group_limit is not None:
                limit = money(group_limit)
                consumed = ZERO
                for item in connection.execute("SELECT request_id, payload_json FROM job_requests"):
                    other = JobRequest.model_validate_json(item["payload_json"])
                    if other.scope == request.scope and other.currency == request.currency:
                        view = self._cost_view(connection, other.requestId)
                        if "BUDGET_BREACH" in view.reasonCodes or "UNBOUNDED_EXPOSURE" in view.reasonCodes:
                            raise BudgetExhausted("group has unresolved unbounded exposure or a budget breach")
                        consumed = total((consumed, total(self._budget_totals(connection, other.requestId))))
                if consumed + reservation > limit:
                    raise BudgetExhausted("shared provider budget exhausted")
            attempt = JobAttempt(
                attemptId=str(uuid.uuid4()),
                requestId=request.requestId,
                status="submitted",
                reservedCost=float(reservation),
                sequence=sequence,
                ownerId=owner_id,
                leaseExpiresAt=now_epoch + max(0.0, lease_seconds),
                dispatchStarted=False,
            )
            self._insert_attempt(connection, attempt, now)
            self._insert_charge(connection, request.requestId, attempt.attemptId, "reserved", reservation)
            return attempt

    def submit(self, request: JobRequest) -> JobAttempt:
        return self.admit(request, mode="submit", owner_id="legacy", lease_seconds=60.0)

    def retry(self, request_id: str) -> JobAttempt:
        return self.admit(
            self.request(request_id),
            mode="retry",
            owner_id=f"job:{request_id}",
            lease_seconds=60.0,
        )

    def claim_dispatch(self, request_id: str, *, owner_id: str, phase: Literal["validating", "running"] = "validating") -> bool:
        """Atomically claim a new dispatch; cancellation is checked in the same transaction."""
        with self._transaction() as connection:
            current = self._attempt_from_row(self._attempt_or_latest_row(connection, request_id))
            if current.dispatchStarted is not False:
                return False
            if self._cancel_requested(connection, request_id):
                if current.status in {"submitted", "cancelling"}:
                    self._transition(connection, current.attemptId, expected_revision=current.revision,
                        owner_id=owner_id, status="cancelled", noChargeReason="NO_DISPATCH_CONFIRMED")
                return False
            if current.status != "submitted":
                return False
            self._transition(connection, current.attemptId, expected_revision=current.revision,
                             owner_id=owner_id, status=phase)
            return True

    def transition(self, attempt_id: str, *, expected_revision: int, owner_id: str,
                   status: JobStatus, **updates: Any) -> JobAttempt:
        with self._transaction() as connection:
            return self._transition(connection, attempt_id, expected_revision=expected_revision,
                owner_id=owner_id, status=status, **updates)

    def _transition(self, connection, attempt_id, *, expected_revision, owner_id, status, **updates):
        now_epoch = time.time()
        row = self._attempt_or_latest_row(connection, attempt_id)
        current = self._attempt_from_row(row)
        if current.revision != expected_revision:
            raise StaleTransition(expected=expected_revision, actual=current.revision)
        if (
            current.ownerId is not None
            and owner_id != current.ownerId
            and (current.leaseExpiresAt is None or current.leaseExpiresAt >= now_epoch)
        ):
            raise NotOwner("attempt lease belongs to another owner")
        if current.status == "outcome_unknown" and status != "outcome_unknown":
            raise ReconciliationRequired("reconcile outcome-unknown attempt before transition")
        if current.status in {"complete", "failed", "cancelled"} and status not in {
            current.status, "outcome_unknown"
        }:
            raise ReconciliationRequired("terminal execution cannot be restarted by transition")
        if current.status not in {"complete", "failed", "cancelled"} and self._cancel_requested(connection, current.requestId) and status not in {
            "cancelled",
            "cancelling",
            "outcome_unknown",
        }:
            status = "cancelling"
        no_charge_reason = updates.pop("noChargeReason", None)
        updates.pop("dispatchStarted", None)  # Server-owned dispatch evidence.
        if status in (_RUNNING_STATUSES - {"cancelling"}) | {"outcome_unknown"}:
            updates["dispatchStarted"] = True
        actual = updates.get("actualCost")
        if actual is not None:
            money(actual)
        if status == "outcome_unknown":
            updates.update(actualCost=None, reconciled=False)
        updated = current.model_copy(
            update={
                "status": status,
                "ownerId": owner_id,
                "revision": current.revision + 1,
                **updates,
            }
        )
        if status == "outcome_unknown" and current.status != "outcome_unknown":
            self._mark_unsettled(connection, updated)
        elif status in {"complete", "failed", "cancelled"} and current.status not in {"complete", "failed", "cancelled"}:
            self._settle_attempt(connection, updated, updates.get("actualCost"),
                                 no_charge_reason=no_charge_reason)
        if status in {"complete", "failed", "cancelled", "outcome_unknown"}:
            billed = self._billing_state(connection, updated)
            updated = updated.model_copy(update={"actualCost": float(billed.settled) if billed.complete else None})
        cursor = connection.execute(
            """
            UPDATE job_attempts
            SET status=?, owner_id=?, lease_expires_at=?, revision=?, reconciled=?,
                payload_json=?, updated_at=?
            WHERE attempt_id=? AND revision=?
            """,
            (
                updated.status,
                updated.ownerId,
                updated.leaseExpiresAt,
                updated.revision,
                int(updated.reconciled),
                updated.model_dump_json(),
                _now(),
                current.attemptId,
                expected_revision,
            ),
        )
        if cursor.rowcount != 1:
            actual = connection.execute(
                "SELECT revision FROM job_attempts WHERE attempt_id=?", (current.attemptId,)
            ).fetchone()
            raise StaleTransition(
                expected=expected_revision,
                actual=int(actual["revision"]),
            )
        return updated

    def heartbeat(self, attempt_id: str, *, owner_id: str, lease_seconds: float) -> None:
        with self._transaction() as connection:
            row = self._attempt_or_latest_row(connection, attempt_id)
            current = self._attempt_from_row(row)
            if current.ownerId != owner_id:
                raise NotOwner("attempt lease belongs to another owner")
            lease = time.time() + max(0.0, lease_seconds)
            updated = current.model_copy(update={"leaseExpiresAt": lease})
            connection.execute(
                "UPDATE job_attempts SET lease_expires_at=?, payload_json=?, updated_at=? WHERE attempt_id=?",
                (lease, updated.model_dump_json(), _now(), current.attemptId),
            )

    def reclaim_expired(self, *, now: float) -> list[JobAttempt]:
        reclaimed: list[JobAttempt] = []
        placeholders = ",".join("?" for _ in _RUNNING_STATUSES)
        with self._transaction() as connection:
            rows = connection.execute(
                f"SELECT * FROM job_attempts WHERE status IN ({placeholders}) AND lease_expires_at < ?",
                (*sorted(_RUNNING_STATUSES), now),
            ).fetchall()
            for row in rows:
                current = self._attempt_from_row(row)
                updated = current.model_copy(
                    update={
                        "status": "outcome_unknown",
                        "error": "lease_expired",
                        "cleanupResult": "unknown",
                        "revision": current.revision + 1,
                    }
                )
                connection.execute(
                    """
                    UPDATE job_attempts SET status=?, revision=?, payload_json=?, updated_at=?
                    WHERE attempt_id=? AND revision=?
                    """,
                    (
                        updated.status,
                        updated.revision,
                        updated.model_dump_json(),
                        _now(),
                        current.attemptId,
                        current.revision,
                    ),
                )
                self._mark_unsettled(connection, updated)
                reclaimed.append(updated)
        return reclaimed

    def reconcile_attempt(self, attempt_id: str, *, provider_outcome, settled_cost,
                          billing_complete: bool = True, receipt_id: str | None = None,
                          no_charge_reason: str | None = None) -> JobAttempt:
        if provider_outcome not in {"complete", "failed", "not_found"}:
            raise ValueError("invalid provider outcome")
        if type(billing_complete) is not bool:
            raise ValueError("billing_complete must be boolean")
        if settled_cost is None and no_charge_reason == "PROVIDER_CONFIRMED_NO_CHARGE":
            settled_cost = ZERO
        exact = None if settled_cost is None else money(settled_cost)
        with self._transaction() as connection:
            current = self._attempt_from_row(self._attempt_or_latest_row(connection, attempt_id))
            if exact is None:
                # Execution outcome says nothing about the absent invoice.
                if not self._billing_state(connection, current).complete:
                    self._mark_unsettled(connection, current, reason="USAGE_PENDING")
                return current
            identity = receipt_id or "legacy-invoice:" + _payload_sha256(json.dumps(
                [current.attemptId, provider_outcome, text(exact), billing_complete, no_charge_reason]))
            inserted = self._apply_invoice(connection, current, exact, final=billing_complete,
                                           receipt_id=identity, reason=no_charge_reason or "PROVIDER_INVOICE")
            if not inserted:
                return current  # Historical replay must not clear later uncertainty.
            updated = current.model_copy(update={
                "status": ("complete" if provider_outcome == "complete" else "failed") if billing_complete else current.status,
                "actualCost": float(exact) if billing_complete else None,
                "reconciled": billing_complete, "revision": current.revision + 1,
                "error": None if provider_outcome == "complete" else provider_outcome})
            connection.execute("UPDATE job_attempts SET status=?, revision=?, reconciled=?, payload_json=?, updated_at=? WHERE attempt_id=?",
                (updated.status, updated.revision, int(updated.reconciled), updated.model_dump_json(), _now(), updated.attemptId))
            return updated


    def record_charge(self, attempt_id: str, *, kind, amount, evidence_id: str | None = None) -> None:
        exact = money(amount)
        if kind not in {"reserved", "estimated", "unsettled", "settled", "released"}:
            raise ValueError("unknown charge kind")
        with self._transaction() as connection:
            row = self._attempt_or_latest_row(connection, attempt_id)
            attempt = self._attempt_from_row(row)
            if evidence_id is not None:
                identity = json.dumps([attempt.attemptId, kind, text(exact)])
                previous = connection.execute("SELECT payload_json FROM job_charge_receipts WHERE receipt_id=?", (evidence_id,)).fetchone()
                if previous is not None:
                    if previous["payload_json"] != identity:
                        raise IdempotencyConflict(evidence_id)
                    return
                connection.execute("INSERT INTO job_charge_receipts VALUES (?,?)", (evidence_id, identity))
            if kind == "settled":
                # Increment identity is independent of the subsequently accumulated subtotal.
                # A replay must compare the original input, not recalculate a different invoice.
                event_id = evidence_id or str(uuid.uuid4())
                old = connection.execute("SELECT evidence_json FROM job_billing_events WHERE event_id=?", (event_id,)).fetchone()
                input_evidence = {"increment": text(exact)}
                if old is not None:
                    original = json.loads(old["evidence_json"])
                    if (original.get("attemptId") != attempt.attemptId
                            or original.get("state") != "partial"
                            or original.get("reason") != "PARTIAL_INVOICE"
                            or original.get("input") != input_evidence):
                        raise IdempotencyConflict(event_id)
                    return
                self._apply_invoice(connection, attempt,
                    total((self._attempt_charge_total(connection, attempt.attemptId, "settled"), exact)),
                    final=False, receipt_id=event_id, reason="PARTIAL_INVOICE", input_evidence=input_evidence)
                return
            if kind == "reserved":
                request = JobRequest.model_validate_json(connection.execute(
                    "SELECT payload_json FROM job_requests WHERE request_id=?", (attempt.requestId,)).fetchone()["payload_json"])
                settled, outstanding, unsettled = self._budget_totals(connection, attempt.requestId)
                if exact > money(request.budget) - settled - outstanding - unsettled:
                    raise BudgetExhausted("charge exceeds authorised budget")
            if kind in {"released", "unsettled"} and exact > self._attempt_outstanding(connection, attempt.attemptId):
                raise BudgetExhausted("charge exceeds reserved amount")
            self._insert_charge(connection, attempt.requestId, attempt.attemptId, kind, exact)
            if kind == "unsettled":
                self._billing_event(connection, attempt, state="unknown", amount=None,
                                    event_id=evidence_id or str(uuid.uuid4()), reason="PROVIDER_OUTCOME_UNKNOWN")


    def timeout_before_response(self, request_id: str, *, owner_id: str) -> JobAttempt:
        attempt = self.latest_attempt(request_id)
        return self.transition(
            attempt.attemptId,
            expected_revision=attempt.revision,
            owner_id=owner_id,
            status="outcome_unknown",
            error="timeout_before_response",
            cleanupResult="unknown",
        )

    def lost_connection(self, request_id: str, *, owner_id: str) -> JobAttempt:
        attempt = self.latest_attempt(request_id)
        return self.transition(
            attempt.attemptId,
            expected_revision=attempt.revision,
            owner_id=owner_id,
            status="outcome_unknown",
            error="lost_connection",
            cleanupResult="unknown",
        )

    def cancel(self, request_id: str) -> JobAttempt:
        result = self.request_cancel(request_id)
        if result is None:
            raise KeyError(request_id)
        return result

    def request_cancel(self, request_id: str) -> JobAttempt | None:
        with self._transaction() as connection:
            row = self._latest_attempt_row(connection, request_id)
            if row is None:
                return None
            latest = self._attempt_from_row(row)
            connection.execute("INSERT INTO job_cancels (request_id, requested_at) VALUES (?, ?) ON CONFLICT(request_id) DO NOTHING", (request_id, _now()))
            if latest.status in {"complete", "failed", "cancelled", "outcome_unknown"}:
                return latest
            return self._transition(connection, latest.attemptId, expected_revision=latest.revision,
                                    owner_id=latest.ownerId or "control-plane", status="cancelling")


    def confirm_termination(self, request_id: str, *, owner_id: str, cost_known: bool = True) -> JobAttempt:
        with self._transaction() as connection:
            attempt = self._attempt_from_row(self._attempt_or_latest_row(connection, request_id))
            terminal = attempt.status in {"complete", "failed", "cancelled", "outcome_unknown"}
            result = self._transition(connection, attempt.attemptId, expected_revision=attempt.revision,
                owner_id=owner_id, status=attempt.status if terminal else "cancelled" if cost_known else "outcome_unknown",
                error=attempt.error if terminal else None if cost_known else "cancelled_cost_unsettled")
            connection.execute("UPDATE job_cancels SET termination_confirmed_at=? WHERE request_id=?", (_now(), request_id))
            return result


    def confirm_cleanup(self, request_id: str, *, owner_id: str, ok: bool) -> JobAttempt:
        result = "confirmed" if ok else "failed"
        with self._transaction() as connection:
            current = self._attempt_from_row(self._attempt_or_latest_row(connection, request_id))
            updated = self._transition(connection, current.attemptId, expected_revision=current.revision,
                                       owner_id=owner_id, status=current.status, cleanupResult=result)
            connection.execute("UPDATE job_cancels SET cleanup_confirmed_at=?, cleanup_result=? WHERE request_id=?", (_now(), result, request_id))
            return updated


    @staticmethod
    def _attempt_from_row(row: sqlite3.Row) -> JobAttempt:
        return JobAttempt.model_validate_json(row["payload_json"])

    @staticmethod
    def _latest_attempt_row(
        connection: sqlite3.Connection, request_id: str
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM job_attempts WHERE request_id=? ORDER BY sequence DESC LIMIT 1",
            (request_id,),
        ).fetchone()

    def _attempt_or_latest_row(
        self, connection: sqlite3.Connection, attempt_or_request_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM job_attempts WHERE attempt_id=?", (attempt_or_request_id,)
        ).fetchone()
        if row is None:
            row = self._latest_attempt_row(connection, attempt_or_request_id)
        if row is None:
            raise KeyError(attempt_or_request_id)
        return row

    @staticmethod
    def _insert_attempt(
        connection: sqlite3.Connection, attempt: JobAttempt, recorded_at: str
    ) -> None:
        connection.execute(
            """
            INSERT INTO job_attempts (
                attempt_id, request_id, sequence, status, owner_id, lease_expires_at,
                revision, reconciled, payload_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attempt.attemptId,
                attempt.requestId,
                attempt.sequence,
                attempt.status,
                attempt.ownerId,
                attempt.leaseExpiresAt,
                attempt.revision,
                int(attempt.reconciled),
                attempt.model_dump_json(),
                recorded_at,
            ),
        )

    @staticmethod
    def _insert_charge(connection, request_id, attempt_id, kind, amount):
        exact = None if amount is None else money(amount, signed=kind == "unsettled")
        connection.execute(
            "INSERT INTO job_charges (charge_id,request_id,attempt_id,kind,amount,recorded_at,amount_exact) VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), request_id, attempt_id, kind,
             None if exact is None else float(exact), _now(), None if exact is None else text(exact)))


    @staticmethod
    def _charge_totals(connection, *, request_id=None, attempt_id=None):
        clause = "request_id=?" if request_id is not None else "attempt_id=?"
        value = request_id if request_id is not None else attempt_id
        totals = {kind: ZERO for kind in ("reserved", "estimated", "unsettled", "settled", "released")}
        for row in connection.execute(f"SELECT kind, amount, amount_exact FROM job_charges WHERE {clause}", (value,)):
            if row["amount"] is not None or row["amount_exact"] is not None:
                totals[row["kind"]] = total((totals[row["kind"]], money(
                    row["amount_exact"] if row["amount_exact"] is not None else row["amount"], signed=True)))
        return totals


    def _budget_totals(self, connection, request_id):
        states = [self._billing_state(connection, self._attempt_from_row(row)) for row in
                  connection.execute("SELECT * FROM job_attempts WHERE request_id=?", (request_id,))]
        return (total(s.settled for s in states), total(s.outstanding for s in states), total(s.unsettled for s in states))


    def _attempt_charge_total(
        self, connection: sqlite3.Connection, attempt_id: str, kind: str
    ) -> float:
        return self._charge_totals(connection, attempt_id=attempt_id)[kind]

    def _attempt_outstanding(self, connection: sqlite3.Connection, attempt_id: str) -> float:
        totals = self._charge_totals(connection, attempt_id=attempt_id)
        return max(
            ZERO,
            totals["reserved"]
            - totals["settled"]
            - totals["released"]
            - max(ZERO, totals["unsettled"]),
        )

    def _mark_unsettled(self, connection, attempt, *, reason="PROVIDER_OUTCOME_UNKNOWN"):
        totals = self._charge_totals(connection, attempt_id=attempt.attemptId)
        exposure = max(ZERO, totals["reserved"] - totals["settled"])
        delta = exposure - totals["unsettled"]
        if delta:
            self._insert_charge(connection, attempt.requestId, attempt.attemptId, "unsettled", delta)
        self._billing_event(connection, attempt, state="unknown", amount=None,
                            event_id=str(uuid.uuid4()), reason=reason)


    def _settle_attempt(self, connection, attempt, actual_cost, *, no_charge_reason=None):
        request = JobRequest.model_validate_json(connection.execute(
            "SELECT payload_json FROM job_requests WHERE request_id=?", (attempt.requestId,)).fetchone()["payload_json"])
        already = self._attempt_charge_total(connection, attempt.attemptId, "settled")
        if actual_cost is None:
            if no_charge_reason == "NO_DISPATCH_CONFIRMED" and already == ZERO:
                actual_cost = ZERO
            elif request.authorisedLocation == "local":
                # Server-admitted local computation has no metered provider dispatch.
                # Preserve any separately recorded charge; do not replace it with zero.
                actual_cost = already
                no_charge_reason = "LOCAL_NON_BILLABLE" if already == ZERO else "LOCAL_FINAL_SETTLEMENT"
            else:
                self._mark_unsettled(connection, attempt, reason="USAGE_PENDING")
                return
        self._apply_invoice(connection, attempt, money(actual_cost), final=True,
                            receipt_id="transition:" + attempt.attemptId + ":" + str(attempt.revision),
                            reason=no_charge_reason or "EXPLICIT_FINAL_INVOICE")


    @staticmethod
    def _cancel_requested(connection: sqlite3.Connection, request_id: str) -> bool:
        return connection.execute(
            "SELECT 1 FROM job_cancels WHERE request_id=?", (request_id,)
        ).fetchone() is not None

    def _attempt_view(self, connection, row):
        attempt = self._attempt_from_row(row)
        billing = self._billing_state(connection, attempt)
        return attempt.model_copy(update={"actualCost": float(billing.settled) if billing.complete else None})

    def _billing_state(self, connection, attempt):
        charges = self._charge_totals(connection, attempt_id=attempt.attemptId)
        latest = connection.execute("SELECT * FROM job_billing_events WHERE attempt_id=? ORDER BY sequence DESC LIMIT 1", (attempt.attemptId,)).fetchone()
        final = latest is not None and latest["state"] == "final"
        uncertain = (latest is not None and latest["state"] in {"partial", "unknown"}) or (
            not final and attempt.status in {"outcome_unknown", "complete", "failed", "cancelled"})
        exposure = max(ZERO, charges["reserved"] - charges["settled"])
        reasons = []
        if final:
            outstanding = unsettled = ZERO
            reasons.append(latest["reason"])
        elif uncertain:
            outstanding, unsettled = ZERO, exposure
            reasons.append(latest["reason"] if latest else "LEGACY_BILLING_UNVERIFIED")
            if exposure == ZERO:
                reasons.append("UNBOUNDED_EXPOSURE")
        else:
            outstanding, unsettled = exposure, ZERO
            reasons.append("IN_PROGRESS")
        if charges["settled"] > charges["reserved"]:
            reasons.append("BUDGET_BREACH")
        return AttemptBilling(charges["settled"], outstanding, unsettled, final, uncertain, tuple(reasons))

    def _cost_view(self, connection, request_id):
        row = connection.execute("SELECT payload_json FROM job_requests WHERE request_id=?", (request_id,)).fetchone()
        if row is None:
            raise KeyError(request_id)
        request = JobRequest.model_validate_json(row["payload_json"])
        states = [self._billing_state(connection, self._attempt_from_row(r)) for r in
                  connection.execute("SELECT * FROM job_attempts WHERE request_id=? ORDER BY sequence", (request_id,))]
        return CostSummary.project(currency=request.currency, budget=money(request.budget), attempts=states)

    def _billing_event(self, connection, attempt, *, state, amount, event_id, reason, input_evidence=None):
        evidence = json.dumps({"attemptId": attempt.attemptId, "state": state,
            "total": None if amount is None else text(amount), "reason": reason,
            **({"input": input_evidence} if input_evidence is not None else {})}, sort_keys=True)
        old = connection.execute("SELECT evidence_json FROM job_billing_events WHERE event_id=?", (event_id,)).fetchone()
        if old:
            if old["evidence_json"] != evidence:
                raise IdempotencyConflict(event_id)
            return False
        connection.execute("INSERT INTO job_billing_events (event_id,request_id,attempt_id,state,total_exact,reason,evidence_json,recorded_at) VALUES (?,?,?,?,?,?,?,?)",
            (event_id, attempt.requestId, attempt.attemptId, state, None if amount is None else text(amount), reason, evidence, _now()))
        return True

    def _apply_invoice(self, connection, attempt, amount, *, final, receipt_id, reason, input_evidence=None):
        # Check the immutable receipt FIRST: replay cannot settle newly discovered uncertainty.
        if not self._billing_event(connection, attempt, state="final" if final else "partial",
                                   amount=amount, event_id=receipt_id, reason=reason, input_evidence=input_evidence):
            return False
        charges = self._charge_totals(connection, attempt_id=attempt.attemptId)
        additional = amount - charges["settled"]
        if additional < ZERO:
            raise ValueError("cumulative invoice cannot reduce known charges without an explicit credit")
        if additional:
            self._insert_charge(connection, attempt.requestId, attempt.attemptId, "settled", additional)
        exposure = ZERO if final else max(ZERO, charges["reserved"] - amount)
        if exposure != charges["unsettled"]:
            self._insert_charge(connection, attempt.requestId, attempt.attemptId, "unsettled", exposure - charges["unsettled"])
        if final:
            released = max(ZERO, charges["reserved"] - amount - charges["released"])
            if released:
                self._insert_charge(connection, attempt.requestId, attempt.attemptId, "released", released)
        return True

    def charges_for(self, attempt_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM job_charges WHERE attempt_id=? ORDER BY recorded_at, charge_id",
                    (attempt_id,),
                )
            ]

    def invalidate_for(self, change: Literal["report", "team_mapping", "track_edit", "calibration", "perception", "ownership"]) -> list[str]:
        return list(REBUILD_FOR[change])

    def receipt(self, request_id: str) -> JobPhase:
        with self._connect() as connection:
            connection.execute("BEGIN")
            request_row = connection.execute(
                "SELECT payload_json FROM job_requests WHERE request_id=?", (request_id,)
            ).fetchone()
            attempt_row = self._latest_attempt_row(connection, request_id)
            if request_row is None or attempt_row is None:
                raise KeyError(request_id)
            request = JobRequest.model_validate_json(request_row["payload_json"])
            attempt = self._attempt_from_row(attempt_row)
            cancel_requested = self._cancel_requested(connection, request_id)
            summary = self._cost_view(connection, request_id)
            attempt_billing = self._billing_state(connection, attempt)
        return JobPhase(
            requestId=request_id,
            attemptId=attempt.attemptId,
            status=attempt.status,
            selectedBackend=attempt.selectedBackend,
            actualHardware=attempt.actualHardware,
            temporalPolicy=request.temporalPolicy,
            fallbackPolicy=request.fallbackPolicy,
            costReserved=attempt.reservedCost,
            costActual=float(attempt_billing.settled) if attempt_billing.complete else None,
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
            **summary.model_dump(),
            costSummary=summary,
            cancelRequested=cancel_requested,
        )

    def cancel_requested(self, request_id: str) -> bool:
        with self._connect() as connection:
            return self._cancel_requested(connection, request_id)

    def terminated(self, request_id: str) -> bool:
        status = self.latest_attempt(request_id).status
        return status in {"cancelled", "complete", "failed"}

    def import_attempt(
        self,
        request_id: str,
        *,
        owner_id: str,
        sha256: str,
        expected_sha256: str,
        schema_ok: bool,
        complete: bool,
    ) -> JobAttempt:
        attempt = self.latest_attempt(request_id)
        if not schema_ok or not complete or sha256 != expected_sha256:
            return self.transition(
                attempt.attemptId,
                expected_revision=attempt.revision,
                owner_id=owner_id,
                status="failed",
                error="quarantined_partial_or_corrupt",
            )
        return self.transition(
            attempt.attemptId,
            expected_revision=attempt.revision,
            owner_id=owner_id,
            status="complete",
        )

    def disk_exhaustion(self, request_id: str, *, owner_id: str) -> JobAttempt:
        attempt = self.latest_attempt(request_id)
        return self.transition(
            attempt.attemptId,
            expected_revision=attempt.revision,
            owner_id=owner_id,
            status="failed",
            error="disk_exhaustion",
        )

    def cost_summary(self, *, match_id: str | None = None) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("BEGIN")
            grouped = {}
            reservations = []
            for row in connection.execute("SELECT payload_json FROM job_requests"):
                req = JobRequest.model_validate_json(row["payload_json"])
                if match_id is not None and req.matchId != match_id:
                    continue
                bucket = grouped.setdefault(req.currency, {"budget": ZERO, "attempts": []})
                bucket["budget"] = total((bucket["budget"], money(req.budget)))
                for item in connection.execute("SELECT * FROM job_attempts WHERE request_id=?", (req.requestId,)):
                    attempt = self._attempt_from_row(item)
                    bucket["attempts"].append(self._billing_state(connection, attempt))
                    reservations.append(attempt.reservedCost)
            summaries = {currency: CostSummary.project(currency=currency, **values).model_dump(mode="json")
                         for currency, values in sorted(grouped.items())}
            if len(summaries) == 1:
                result = dict(next(iter(summaries.values())))
            else:
                result = {"schemaVersion": 2, "currency": None, "authorisedBudget": None,
                    "settledTotal": None, "outstandingReserved": None, "unsettledTotal": None,
                    "reservedTotal": None, "actualTotal": None,
                    "billingComplete": bool(summaries) and all(v["billingComplete"] for v in summaries.values()),
                    "attemptCount": sum(v["attemptCount"] for v in summaries.values()),
                    "unsettledAttemptCount": sum(v["unsettledAttemptCount"] for v in summaries.values()),
                    "reasonCodes": ["MIXED_CURRENCIES"] if summaries else ["NO_BILLING_EVIDENCE"]}
            return {**result, "attempts": result["attemptCount"], "byCurrency": summaries,
                    "p50Reserved": _percentile(reservations, 50) if len(summaries) == 1 else None,
                    "p95Reserved": _percentile(reservations, 95) if len(summaries) == 1 else None}


    def cost_for(self, request_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("BEGIN")
            summary = self._cost_view(connection, request_id)
            reservations = [float(row["reservedCost"]) for row in
                (json.loads(item["payload_json"]) for item in connection.execute(
                    "SELECT payload_json FROM job_attempts WHERE request_id=?", (request_id,)))]
            return {**summary.model_dump(mode="json"), "requestId": request_id,
                "attempts": summary.attemptCount, "p50Reserved": _percentile(reservations, 50),
                "p95Reserved": _percentile(reservations, 95)}



def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_request_json(request: JobRequest) -> str:
    return json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def _payload_sha256(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()


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
    if ledger.has_request(job_id):
        receipt = ledger.receipt(job_id)
        view["cancelRequested"] = receipt.cancelRequested
        view["durablePhase"] = receipt.status
        view["ledgerStatus"] = receipt.status
        view["attemptId"] = receipt.attemptId
        view["costReserved"] = receipt.costReserved
        view["costActual"] = receipt.costActual
        view["costSummary"] = receipt.costSummary.model_dump(mode="json")
        view.update(receipt.costSummary.model_dump(mode="json"))
        view["cleanupResult"] = receipt.cleanupResult
        view["temporalPolicy"] = receipt.temporalPolicy
        view["cacheIdentity"] = receipt.cacheIdentity
        view["terminated"] = receipt.status in {"cancelled", "complete", "failed"}
    else:
        view["cancelRequested"] = ledger.cancel_requested(job_id)
        view["durablePhase"] = None
        view["ledgerStatus"] = None
        view["cleanupResult"] = "unknown"
        view["terminated"] = storage_terminal
        view["costReserved"] = view.get("costReserved", 0.0)
        view["costActual"] = None
        view["actualTotal"] = None
        view["billingComplete"] = False
        view["reasonCodes"] = ["NO_BILLING_EVIDENCE"]
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
