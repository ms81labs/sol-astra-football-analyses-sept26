from __future__ import annotations

import multiprocessing
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.main import create_app
from backend.app.schemas import MatchConfig
from backend.app.workbench.errors import (
    NotOwner,
    ReconciliationRequired,
    RetryBudgetExhausted,
    StaleTransition,
)
from backend.app.storage import Storage
from backend.app.workbench.jobs import DurableJobLedger, JobRequest, maintain_job_lease
from backend.app.workbench.jobs import CostEntry, JobAttempt


def _request(request_id: str, *, budget: float = 1.25) -> JobRequest:
    return JobRequest(
        requestId=request_id,
        matchId="match-1",
        sourceSha256="a" * 64,
        intervalStart=0,
        intervalEnd=10,
        temporalPolicy="source_global_grid",
        decoderVersion="opencv",
        modelHash="weights-v1",
        outputSchema="evidence_v1",
        budget=budget,
        authorisedLocation="local",
    )


def _admit_many(db_path: str, prefix: str, count: int) -> None:
    ledger = DurableJobLedger(db_path=db_path)
    for index in range(count):
        ledger.admit(
            _request(f"{prefix}-{index}", budget=1.0),
            mode="submit",
            owner_id=prefix,
            lease_seconds=60,
        )


def test_legacy_rows_migrate_once_without_constructor_reconciliation(tmp_path: Path) -> None:
    db_path = tmp_path / "jobs.sqlite3"
    request = _request("legacy", budget=1.0)
    attempt = JobAttempt(
        attemptId="legacy-attempt",
        requestId=request.requestId,
        status="running",
        reservedCost=1.0,
    )
    cost = CostEntry(
        requestId=request.requestId,
        attemptId=attempt.attemptId,
        reserved=1.0,
        actual=None,
        scope="job",
    )
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE job_ledger_requests (request_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL);
            CREATE TABLE job_ledger_attempts (
                attempt_id TEXT PRIMARY KEY, request_id TEXT NOT NULL,
                sequence INTEGER NOT NULL, payload_json TEXT NOT NULL);
            CREATE TABLE job_ledger_costs (
                attempt_id TEXT PRIMARY KEY, request_id TEXT NOT NULL, payload_json TEXT NOT NULL);
            CREATE TABLE job_ledger_cancels (request_id TEXT PRIMARY KEY);
            """
        )
        connection.execute(
            "INSERT INTO job_ledger_requests VALUES (?, ?)",
            (request.requestId, request.model_dump_json()),
        )
        connection.execute(
            "INSERT INTO job_ledger_attempts VALUES (?, ?, 0, ?)",
            (attempt.attemptId, request.requestId, attempt.model_dump_json()),
        )
        connection.execute(
            "INSERT INTO job_ledger_costs VALUES (?, ?, ?)",
            (attempt.attemptId, request.requestId, cost.model_dump_json()),
        )

    ledger = DurableJobLedger(db_path)
    assert ledger.receipt(request.requestId).status == "running"
    assert ledger.receipt(request.requestId).attemptCount == 1
    assert DurableJobLedger(db_path).receipt(request.requestId).attemptCount == 1
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM job_ledger_requests").fetchone()[0] == 1


def test_job_budget_rejects_negative_and_nonfinite_values() -> None:
    with pytest.raises(ValidationError):
        _request("negative", budget=-1)
    with pytest.raises(ValidationError):
        _request("infinite", budget=float("inf"))


@pytest.mark.parametrize("status", ["submitted", "running", "complete", "failed", "cancelled"])
def test_t10_submit_replay_never_creates_an_attempt(status: str, tmp_path: Path) -> None:
    ledger = DurableJobLedger(tmp_path / f"{status}.sqlite3")
    request = _request(f"request-{status}", budget=10)
    first = ledger.admit(request, mode="submit", owner_id="owner", lease_seconds=60)
    if status != "submitted":
        first = ledger.transition(
            first.attemptId,
            expected_revision=first.revision,
            owner_id="owner",
            status=status,
            actualCost=0.0 if status in {"complete", "failed", "cancelled"} else None,
        )

    replay = ledger.admit(request, mode="submit", owner_id="other", lease_seconds=60)

    assert replay.attemptId == first.attemptId
    assert len(ledger.attempts[request.requestId]) == 1


def test_t10_unknown_requires_reconciliation_and_retry_cap_is_shared(tmp_path: Path) -> None:
    ledger = DurableJobLedger(tmp_path / "jobs.sqlite3")
    request = _request("request-retry", budget=10)
    attempt = ledger.admit(request, mode="submit", owner_id="owner", lease_seconds=60)
    attempt = ledger.transition(
        attempt.attemptId,
        expected_revision=attempt.revision,
        owner_id="owner",
        status="outcome_unknown",
    )
    with pytest.raises(ReconciliationRequired):
        ledger.admit(request, mode="submit", owner_id="owner", lease_seconds=60)
    with pytest.raises(ReconciliationRequired):
        ledger.admit(request, mode="retry", owner_id="owner", lease_seconds=60)

    ledger.reconcile_attempt(attempt.attemptId, provider_outcome="failed", settled_cost=0.0)
    for _ in range(2):
        attempt = ledger.admit(request, mode="retry", owner_id="owner", lease_seconds=60)
        attempt = ledger.transition(
            attempt.attemptId,
            expected_revision=attempt.revision,
            owner_id="owner",
            status="failed",
            actualCost=0.0,
        )
    with pytest.raises(RetryBudgetExhausted):
        ledger.admit(request, mode="retry", owner_id="owner", lease_seconds=60)


def test_transition_requires_explicit_revision_and_owner(tmp_path: Path) -> None:
    ledger = DurableJobLedger(tmp_path / "jobs.sqlite3")
    attempt = ledger.admit(
        _request("strict-cas"),
        mode="submit",
        owner_id="owner",
        lease_seconds=60,
    )
    with pytest.raises(TypeError):
        ledger.transition(attempt.attemptId, status="running")  # type: ignore[call-arg]


def test_retry_after_cancel_clears_only_the_request_level_cancel_flag(tmp_path: Path) -> None:
    ledger = DurableJobLedger(tmp_path / "jobs.sqlite3")
    request = _request("cancel-retry", budget=2.0)
    first = ledger.admit(request, mode="submit", owner_id="worker", lease_seconds=60)
    ledger.request_cancel(request.requestId)
    ledger.confirm_termination(request.requestId, owner_id="worker")

    retried = ledger.admit(
        request,
        mode="retry",
        owner_id="worker",
        lease_seconds=60,
    )

    assert retried.attemptId != first.attemptId
    assert retried.status == "submitted"
    assert ledger.cancel_requested(request.requestId) is False


def test_t10_retry_route_is_the_only_dispatching_retry(tmp_path: Path, monkeypatch) -> None:
    app = create_app(tmp_path)
    match = app.state.storage.create_match(
        "retry",
        "tracking_json",
        "tracking.json",
        tmp_path / "tracking.json",
        MatchConfig(),
    )
    job, _ = app.state.storage.ensure_job(match.id, "retry-job", budget=2.0)
    first = app.state.runner.ledger.latest_attempt(job.id)
    app.state.runner.ledger.transition(
        first.attemptId,
        expected_revision=first.revision,
        owner_id=f"job:{job.id}",
        status="failed",
        actualCost=0.0,
    )
    dispatched: list[str] = []
    monkeypatch.setattr(app.state.runner, "start", dispatched.append)

    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.post(f"/api/jobs/{job.id}/retry")

    assert response.status_code == 200, response.text
    assert dispatched == [job.id]
    assert app.state.runner.ledger.receipt(job.id).attemptCount == 2
    assert response.json()["status"] == "queued"


def test_storage_ledger_failure_does_not_commit_legacy_status(tmp_path: Path, monkeypatch) -> None:
    storage = Storage(tmp_path)
    match = storage.create_match(
        "authority",
        "tracking_json",
        "tracking.json",
        tmp_path / "tracking.json",
        MatchConfig(),
    )
    job, _ = storage.ensure_job(match.id, "authority-job")

    def stale(*_args, **_kwargs):
        raise StaleTransition(expected=0, actual=1)

    monkeypatch.setattr(storage.job_ledger, "transition", stale)
    with pytest.raises(StaleTransition):
        storage.update_job(job.id, status="processing", progress=0.1)
    assert storage.get_job(job.id).status == "queued"


def test_worker_lease_renews_without_progress_callbacks(tmp_path: Path) -> None:
    ledger = DurableJobLedger(tmp_path / "jobs.sqlite3")
    request = _request("heartbeat")
    attempt = ledger.admit(request, mode="submit", owner_id="worker", lease_seconds=0.15)
    ledger.transition(
        attempt.attemptId,
        expected_revision=attempt.revision,
        owner_id="worker",
        status="running",
    )
    with maintain_job_lease(
        ledger,
        request.requestId,
        owner_id="worker",
        lease_seconds=0.15,
    ):
        time.sleep(0.25)
        assert ledger.reclaim_expired(now=time.time()) == []


def test_unknown_remote_cost_keeps_budget_unsettled(tmp_path: Path) -> None:
    storage = Storage(tmp_path)
    match = storage.create_match(
        "remote",
        "tracking_json",
        "tracking.json",
        tmp_path / "tracking.json",
        MatchConfig(),
    )
    job, _ = storage.ensure_job(
        match.id,
        "remote-job",
        budget=2.0,
        authorised_location="daytona",
    )
    storage.update_job(job.id, status="processing", progress=0.1)
    with storage.remote_cost_unsettled():
        storage.update_job(job.id, status="completed", progress=1.0)
    receipt = storage.job_ledger.receipt(job.id)
    assert receipt.status == "outcome_unknown"
    assert receipt.unsettledTotal == 2.0
    assert receipt.actualTotal is None


@pytest.mark.integration
def test_t11_multiple_processes_share_authority_and_respect_leases(tmp_path: Path) -> None:
    db_path = tmp_path / "jobs.sqlite3"
    parent = DurableJobLedger(db_path)
    request = _request("leased", budget=10)
    attempt = parent.admit(request, mode="submit", owner_id="p1", lease_seconds=60)
    attempt = parent.transition(
        attempt.attemptId,
        expected_revision=attempt.revision,
        owner_id="p1",
        status="running",
    )
    child = DurableJobLedger(db_path)
    assert child.receipt(request.requestId).status == "running"
    with pytest.raises(StaleTransition):
        child.transition(
            attempt.attemptId,
            expected_revision=attempt.revision - 1,
            owner_id="p1",
            status="running",
        )
    with pytest.raises(NotOwner):
        child.transition(
            attempt.attemptId,
            expected_revision=attempt.revision,
            owner_id="p2",
            status="running",
        )
    assert child.reclaim_expired(now=time.time() + 120)[0].status == "outcome_unknown"

    context = multiprocessing.get_context("spawn")
    processes = [
        context.Process(target=_admit_many, args=(str(db_path), prefix, 200))
        for prefix in ("left", "right")
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(30)
        assert process.exitcode == 0
    assert len(parent.requests) == 401


@pytest.mark.integration
def test_t11_transition_write_count_is_constant(tmp_path: Path) -> None:
    ledger = DurableJobLedger(tmp_path / "jobs.sqlite3")
    for index in range(1_000):
        ledger.admit(
            _request(f"history-{index}", budget=1.0),
            mode="submit",
            owner_id="worker",
            lease_seconds=60,
        )
    target = ledger.latest_attempt("history-999")
    statements: list[str] = []
    open_connection = ledger._open_connection

    def traced_connection():
        connection = open_connection()
        connection.set_trace_callback(statements.append)
        return connection

    ledger._open_connection = traced_connection  # type: ignore[method-assign]
    ledger.transition(
        target.attemptId,
        expected_revision=target.revision,
        owner_id="worker",
        status="running",
    )

    writes = [statement for statement in statements if statement.lstrip().upper().startswith("UPDATE")]
    assert len(writes) == 1
    assert "WHERE attempt_id=" in writes[0]
    assert len(statements) <= 12


def test_t12_reservations_never_exceed_authorised_budget(tmp_path: Path) -> None:
    ledger = DurableJobLedger(tmp_path / "jobs.sqlite3")
    request = _request("budgeted")
    first = ledger.admit(request, mode="submit", owner_id="worker", lease_seconds=60)
    assert first.reservedCost == 1.25
    first = ledger.transition(
        first.attemptId,
        expected_revision=first.revision,
        owner_id="worker",
        status="failed",
        actualCost=0.5,
    )
    second = ledger.admit(request, mode="retry", owner_id="worker", lease_seconds=60)
    assert second.reservedCost == 0.75
    second = ledger.transition(
        second.attemptId,
        expected_revision=second.revision,
        owner_id="worker",
        status="failed",
        actualCost=0.5,
    )
    third = ledger.admit(request, mode="retry", owner_id="worker", lease_seconds=60)
    assert third.reservedCost == 0.25
    third = ledger.transition(
        third.attemptId,
        expected_revision=third.revision,
        owner_id="worker",
        status="outcome_unknown",
    )

    receipt = ledger.receipt(request.requestId)
    assert receipt.attemptCount == 3
    assert receipt.settledTotal == 1.0
    assert receipt.unsettledTotal == 0.25
    assert receipt.actualTotal is None
    assert receipt.settledTotal + receipt.reservedTotal + receipt.unsettledTotal <= request.budget
    assert all(ledger.charges_for(item.attemptId) for item in ledger.attempts[request.requestId])

    charge_count = sum(len(ledger.charges_for(item.attemptId)) for item in ledger.attempts[request.requestId])
    with pytest.raises(ReconciliationRequired):
        ledger.admit(request, mode="submit", owner_id="worker", lease_seconds=60)
    assert sum(len(ledger.charges_for(item.attemptId)) for item in ledger.attempts[request.requestId]) == charge_count

    cancelled_request = _request("cancelled-budget", budget=1.25)
    cancelled = ledger.admit(
        cancelled_request,
        mode="submit",
        owner_id="worker",
        lease_seconds=60,
    )
    ledger.record_charge(cancelled.attemptId, kind="settled", amount=0.2)
    ledger.request_cancel(cancelled_request.requestId)
    ledger.confirm_termination(cancelled_request.requestId, owner_id="worker")
    ledger.confirm_cleanup(cancelled_request.requestId, owner_id="worker", ok=True)
    assert ledger.receipt(cancelled_request.requestId).settledTotal == 0.2
