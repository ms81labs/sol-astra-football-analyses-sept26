"""GA-12 durable jobs, cost ledger, selective recomputation and cleanup."""

from __future__ import annotations

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

from pydantic import Field

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
    sequence: int = 1
    ownerId: str | None = None
    leaseExpiresAt: float | None = None
    revision: int = 0
    reconciled: bool = False


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
        self._migrate_legacy_once()

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
                pass
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
                CREATE TABLE IF NOT EXISTS job_cancels (
                    request_id TEXT PRIMARY KEY REFERENCES job_requests(request_id),
                    requested_at TEXT NOT NULL,
                    termination_confirmed_at TEXT,
                    cleanup_confirmed_at TEXT,
                    cleanup_result TEXT
                );
                """
            )

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
            for row in connection.execute(
                "SELECT request_id, payload_json FROM job_attempts ORDER BY request_id, sequence"
            ):
                result.setdefault(row["request_id"], []).append(
                    JobAttempt.model_validate_json(row["payload_json"])
                )
        return result

    @property
    def costs(self) -> list[CostEntry]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT a.request_id, a.attempt_id,
                       COALESCE(SUM(CASE WHEN c.kind='reserved' THEN c.amount ELSE 0 END), 0) reserved,
                       SUM(CASE WHEN c.kind='settled' THEN c.amount END) actual
                FROM job_attempts a LEFT JOIN job_charges c ON c.attempt_id=a.attempt_id
                GROUP BY a.request_id, a.attempt_id ORDER BY a.request_id, a.sequence
                """
            ).fetchall()
        return [
            CostEntry(
                requestId=row["request_id"],
                attemptId=row["attempt_id"],
                reserved=float(row["reserved"]),
                actual=None if row["actual"] is None else float(row["actual"]),
                scope="job",
            )
            for row in rows
        ]

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
            row = self._latest_attempt_row(connection, request_id)
        if row is None:
            raise KeyError(request_id)
        return self._attempt_from_row(row)

    def admit(
        self,
        request: JobRequest,
        *,
        mode: Literal["submit", "retry"],
        owner_id: str,
        lease_seconds: float,
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
                connection.execute(
                    "INSERT INTO job_requests VALUES (?, ?, ?, ?, 0, ?)",
                    (request.requestId, payload, payload_sha, request.budget, now),
                )
                latest = None
                sequence = 1
            else:
                if request_row["payload_sha256"] != payload_sha:
                    raise IdempotencyConflict(request.requestId)
                latest_row = self._latest_attempt_row(connection, request.requestId)
                latest = None if latest_row is None else self._attempt_from_row(latest_row)
                sequence = 1 if latest is None else latest.sequence + 1
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
            settled, reserved, unsettled = self._budget_totals(connection, request.requestId)
            remaining = max(0.0, request.budget - settled - reserved - unsettled)
            reservation = min(request.budget, remaining)
            if request.budget > 0 and reservation <= 0:
                raise BudgetExhausted("authorised budget exhausted")
            attempt = JobAttempt(
                attemptId=str(uuid.uuid4()),
                requestId=request.requestId,
                status="submitted",
                reservedCost=reservation,
                sequence=sequence,
                ownerId=owner_id,
                leaseExpiresAt=now_epoch + max(0.0, lease_seconds),
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

    def transition(
        self,
        attempt_id: str,
        *,
        expected_revision: int,
        owner_id: str,
        status: JobStatus,
        **updates: Any,
    ) -> JobAttempt:
        now_epoch = time.time()
        with self._transaction() as connection:
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
            if self._cancel_requested(connection, current.requestId) and status not in {
                "cancelled",
                "cancelling",
                "outcome_unknown",
            }:
                status = "cancelling"
            updated = current.model_copy(
                update={
                    "status": status,
                    "ownerId": owner_id,
                    "revision": current.revision + 1,
                    **updates,
                }
            )
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
            if status == "outcome_unknown" and current.status != "outcome_unknown":
                self._mark_unsettled(connection, updated)
            elif status in {"complete", "failed", "cancelled"} and current.status not in {
                "complete",
                "failed",
                "cancelled",
            }:
                self._settle_attempt(connection, updated, updates.get("actualCost"))
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

    def reconcile_attempt(
        self,
        attempt_id: str,
        *,
        provider_outcome: Literal["complete", "failed", "not_found"],
        settled_cost: float | None,
    ) -> JobAttempt:
        with self._transaction() as connection:
            row = self._attempt_or_latest_row(connection, attempt_id)
            current = self._attempt_from_row(row)
            if current.status != "outcome_unknown":
                return current
            unsettled = self._attempt_charge_total(connection, current.attemptId, "unsettled")
            if unsettled:
                self._insert_charge(
                    connection, current.requestId, current.attemptId, "unsettled", -unsettled
                )
            already_settled = self._attempt_charge_total(
                connection, current.attemptId, "settled"
            )
            cost = already_settled if settled_cost is None else float(settled_cost)
            additional = cost - already_settled
            if additional < -1e-9 or additional > unsettled + 1e-9:
                raise BudgetExhausted("settled cost exceeds reserved amount")
            if additional > 0:
                self._insert_charge(
                    connection, current.requestId, current.attemptId, "settled", additional
                )
            if unsettled - additional > 0:
                self._insert_charge(
                    connection,
                    current.requestId,
                    current.attemptId,
                    "released",
                    unsettled - additional,
                )
            updated = current.model_copy(
                update={
                    "status": "complete" if provider_outcome == "complete" else "failed",
                    "actualCost": cost,
                    "reconciled": True,
                    "revision": current.revision + 1,
                    "error": None if provider_outcome == "complete" else provider_outcome,
                }
            )
            connection.execute(
                """
                UPDATE job_attempts SET status=?, revision=?, reconciled=1, payload_json=?, updated_at=?
                WHERE attempt_id=?
                """,
                (updated.status, updated.revision, updated.model_dump_json(), _now(), current.attemptId),
            )
            return updated

    def record_charge(
        self,
        attempt_id: str,
        *,
        kind: Literal["reserved", "estimated", "unsettled", "settled", "released"],
        amount: float | None,
    ) -> None:
        if amount is None or amount < 0:
            raise ValueError("charge amount must be non-negative")
        with self._transaction() as connection:
            row = self._attempt_or_latest_row(connection, attempt_id)
            request_id = row["request_id"]
            if kind == "reserved":
                budget = float(
                    connection.execute(
                        "SELECT authorised_budget FROM job_requests WHERE request_id=?",
                        (request_id,),
                    ).fetchone()["authorised_budget"]
                )
                settled, reserved, unsettled = self._budget_totals(connection, request_id)
                if amount > budget - settled - reserved - unsettled + 1e-9:
                    raise BudgetExhausted("charge exceeds authorised budget")
            elif kind in {"settled", "unsettled", "released"}:
                outstanding = self._attempt_outstanding(connection, row["attempt_id"])
                if amount > outstanding + 1e-9:
                    raise BudgetExhausted("charge exceeds reserved amount")
            self._insert_charge(connection, request_id, row["attempt_id"], kind, amount)

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
            connection.execute(
                """
                INSERT INTO job_cancels (request_id, requested_at) VALUES (?, ?)
                ON CONFLICT(request_id) DO NOTHING
                """,
                (request_id, _now()),
            )
            row = self._latest_attempt_row(connection, request_id)
        if row is None:
            return None
        latest = self._attempt_from_row(row)
        if latest.status in {"complete", "failed", "cancelled", "outcome_unknown"}:
            return latest
        return self.transition(
            latest.attemptId,
            expected_revision=latest.revision,
            owner_id=latest.ownerId or "control-plane",
            status="cancelling",
        )

    def confirm_termination(
        self, request_id: str, *, owner_id: str, cost_known: bool = True
    ) -> JobAttempt:
        with self._transaction() as connection:
            connection.execute(
                "UPDATE job_cancels SET termination_confirmed_at=? WHERE request_id=?",
                (_now(), request_id),
            )
            row = self._latest_attempt_row(connection, request_id)
        attempt = self._attempt_from_row(row)
        return self.transition(
            attempt.attemptId,
            expected_revision=attempt.revision,
            owner_id=owner_id,
            status="cancelled" if cost_known else "outcome_unknown",
            error=None if cost_known else "cancelled_cost_unsettled",
        )

    def confirm_cleanup(self, request_id: str, *, owner_id: str, ok: bool) -> JobAttempt:
        result = "confirmed" if ok else "failed"
        with self._transaction() as connection:
            connection.execute(
                "UPDATE job_cancels SET cleanup_confirmed_at=?, cleanup_result=? WHERE request_id=?",
                (_now(), result, request_id),
            )
            row = self._latest_attempt_row(connection, request_id)
        current = self._attempt_from_row(row)
        return self.transition(
            current.attemptId,
            expected_revision=current.revision,
            owner_id=owner_id,
            status=current.status,
            cleanupResult=result,
        )

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
    def _insert_charge(
        connection: sqlite3.Connection,
        request_id: str,
        attempt_id: str,
        kind: str,
        amount: float | None,
    ) -> None:
        connection.execute(
            "INSERT INTO job_charges VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), request_id, attempt_id, kind, amount, _now()),
        )

    @staticmethod
    def _charge_totals(
        connection: sqlite3.Connection, *, request_id: str | None = None, attempt_id: str | None = None
    ) -> dict[str, float]:
        clause = "request_id=?" if request_id is not None else "attempt_id=?"
        value = request_id if request_id is not None else attempt_id
        rows = connection.execute(
            f"SELECT kind, COALESCE(SUM(amount), 0) total FROM job_charges WHERE {clause} GROUP BY kind",
            (value,),
        )
        totals = {kind: 0.0 for kind in ("reserved", "estimated", "unsettled", "settled", "released")}
        totals.update({row["kind"]: float(row["total"]) for row in rows})
        return totals

    def _budget_totals(
        self, connection: sqlite3.Connection, request_id: str
    ) -> tuple[float, float, float]:
        totals = self._charge_totals(connection, request_id=request_id)
        unsettled = max(0.0, totals["unsettled"])
        outstanding = max(
            0.0,
            totals["reserved"] - totals["settled"] - totals["released"] - unsettled,
        )
        return totals["settled"], outstanding, unsettled

    def _attempt_charge_total(
        self, connection: sqlite3.Connection, attempt_id: str, kind: str
    ) -> float:
        return self._charge_totals(connection, attempt_id=attempt_id)[kind]

    def _attempt_outstanding(self, connection: sqlite3.Connection, attempt_id: str) -> float:
        totals = self._charge_totals(connection, attempt_id=attempt_id)
        return max(
            0.0,
            totals["reserved"]
            - totals["settled"]
            - totals["released"]
            - max(0.0, totals["unsettled"]),
        )

    def _mark_unsettled(self, connection: sqlite3.Connection, attempt: JobAttempt) -> None:
        outstanding = self._attempt_outstanding(connection, attempt.attemptId)
        if outstanding:
            self._insert_charge(
                connection, attempt.requestId, attempt.attemptId, "unsettled", outstanding
            )

    def _settle_attempt(
        self, connection: sqlite3.Connection, attempt: JobAttempt, actual_cost: Any
    ) -> None:
        outstanding = self._attempt_outstanding(connection, attempt.attemptId)
        already_settled = self._attempt_charge_total(connection, attempt.attemptId, "settled")
        cost = already_settled if actual_cost is None else float(actual_cost)
        additional = cost - already_settled
        if additional < -1e-9 or additional > outstanding + 1e-9:
            raise BudgetExhausted("settled cost exceeds reserved amount")
        if additional > 0:
            self._insert_charge(
                connection, attempt.requestId, attempt.attemptId, "settled", additional
            )
        if outstanding - additional > 0:
            self._insert_charge(
                connection,
                attempt.requestId,
                attempt.attemptId,
                "released",
                outstanding - additional,
            )

    @staticmethod
    def _cancel_requested(connection: sqlite3.Connection, request_id: str) -> bool:
        return connection.execute(
            "SELECT 1 FROM job_cancels WHERE request_id=?", (request_id,)
        ).fetchone() is not None

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
            request_row = connection.execute(
                "SELECT payload_json FROM job_requests WHERE request_id=?", (request_id,)
            ).fetchone()
            attempt_row = self._latest_attempt_row(connection, request_id)
            if request_row is None or attempt_row is None:
                raise KeyError(request_id)
            request = JobRequest.model_validate_json(request_row["payload_json"])
            attempt = self._attempt_from_row(attempt_row)
            attempt_count = int(
                connection.execute(
                    "SELECT COUNT(*) count FROM job_attempts WHERE request_id=?", (request_id,)
                ).fetchone()["count"]
            )
            settled, reserved, unsettled = self._budget_totals(connection, request_id)
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
            attemptCount=attempt_count,
            reservedTotal=round(reserved, 4),
            settledTotal=round(settled, 4),
            unsettledTotal=round(unsettled, 4),
            actualTotal=None if unsettled > 0 else round(settled, 4),
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

    def cost_summary(self) -> dict[str, float | int]:
        with self._connect() as connection:
            request_ids = [row["request_id"] for row in connection.execute("SELECT request_id FROM job_requests")]
            budget_totals = [self._budget_totals(connection, request_id) for request_id in request_ids]
            reservations = [
                float(row["amount"] or 0.0)
                for row in connection.execute("SELECT amount FROM job_charges WHERE kind='reserved'")
            ]
        return {
            "attempts": len(reservations),
            "reservedTotal": round(sum(item[1] + item[2] for item in budget_totals), 4),
            "actualTotal": round(sum(item[0] for item in budget_totals), 4),
            "p50Reserved": _percentile(reservations, 50),
            "p95Reserved": _percentile(reservations, 95),
        }

    def cost_for(self, request_id: str) -> dict[str, float | int | str]:
        with self._connect() as connection:
            settled, reserved, unsettled = self._budget_totals(connection, request_id)
            reservations = [
                float(row["amount"] or 0.0)
                for row in connection.execute(
                    "SELECT amount FROM job_charges WHERE request_id=? AND kind='reserved'",
                    (request_id,),
                )
            ]
        return {
            "requestId": request_id,
            "attempts": len(reservations),
            "reservedTotal": round(reserved + unsettled, 4),
            "actualTotal": round(settled, 4),
            "p50Reserved": _percentile(reservations, 50),
            "p95Reserved": _percentile(reservations, 95),
        }


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
    view["cancelRequested"] = ledger.cancel_requested(job_id)
    if ledger.has_request(job_id):
        receipt = ledger.receipt(job_id)
        view["durablePhase"] = receipt.status
        view["ledgerStatus"] = receipt.status
        view["attemptId"] = receipt.attemptId
        view["costReserved"] = receipt.costReserved
        view["costActual"] = receipt.costActual
        view["cleanupResult"] = receipt.cleanupResult
        view["temporalPolicy"] = receipt.temporalPolicy
        view["cacheIdentity"] = receipt.cacheIdentity
        view["terminated"] = ledger.terminated(job_id)
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
