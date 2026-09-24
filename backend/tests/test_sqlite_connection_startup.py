"""Connection ownership and transient WAL-startup contention regressions."""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

import pytest

from backend.app.storage import Storage
from backend.app.workbench.jobs import DurableJobLedger


class _ObservedConnection:
    def __init__(self, connection, failure, fail_sql):
        self.connection = connection
        self.failure = failure
        self.fail_sql = fail_sql
        self.closed = False
        self.commands = []

    @property
    def row_factory(self):
        return self.connection.row_factory

    @row_factory.setter
    def row_factory(self, value):
        self.connection.row_factory = value

    def execute(self, sql, *args):
        self.commands.append(sql)
        if sql == self.fail_sql and self.failure is not None:
            raise self.failure
        return self.connection.execute(sql, *args)

    def close(self):
        self.closed = True
        self.connection.close()


@pytest.fixture(params=[Storage, DurableJobLedger], ids=["storage", "ledger"])
def connection_owner(request, tmp_path: Path):
    owner = object.__new__(request.param)
    owner.db_path = tmp_path / "startup.sqlite3"
    return owner


def _sqlite_error(code):
    error = sqlite3.OperationalError("controlled setup failure")
    if code is not None:
        error.sqlite_errorcode = code
    return error


def _observe_connections(monkeypatch, failures, *, fail_sql="PRAGMA journal_mode=WAL"):
    original = sqlite3.connect
    opened = []
    timeouts = []
    pending = iter(failures)

    def connect(*args, **kwargs):
        timeouts.append(kwargs["timeout"])
        wrapped = _ObservedConnection(original(*args, **kwargs), next(pending, None), fail_sql)
        opened.append(wrapped)
        return wrapped

    monkeypatch.setattr(sqlite3, "connect", connect)
    return opened, timeouts


@pytest.mark.parametrize("code", [sqlite3.SQLITE_BUSY, sqlite3.SQLITE_BUSY_RECOVERY, sqlite3.SQLITE_BUSY_SNAPSHOT])
def test_transient_wal_busy_retries_a_fresh_closed_connection(connection_owner, monkeypatch, code):
    opened, timeouts = _observe_connections(monkeypatch, [_sqlite_error(code), None])
    connection = connection_owner._open_connection()
    try:
        assert len(opened) == 2
        assert opened[0].closed and not opened[1].closed
        assert connection is opened[1]
        assert 0 <= timeouts[1] <= timeouts[0] <= 30
        assert connection.row_factory is sqlite3.Row
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == isinstance(connection_owner, DurableJobLedger)
    finally:
        connection.close()


@pytest.mark.parametrize("code", [sqlite3.SQLITE_LOCKED, sqlite3.SQLITE_IOERR, sqlite3.SQLITE_READONLY, None])
def test_other_setup_errors_are_closed_and_propagated_without_retry(connection_owner, monkeypatch, code):
    failure = _sqlite_error(code)
    opened, _ = _observe_connections(monkeypatch, [failure])
    with pytest.raises(sqlite3.OperationalError) as caught:
        connection_owner._open_connection()
    assert caught.value is failure
    assert len(opened) == 1 and opened[0].closed


@pytest.mark.parametrize("failure", [sqlite3.DatabaseError("corrupt"), RuntimeError("unexpected")])
def test_non_operational_setup_failures_also_release_connection(connection_owner, monkeypatch, failure):
    opened, _ = _observe_connections(monkeypatch, [failure])
    with pytest.raises(type(failure)) as caught:
        connection_owner._open_connection()
    assert caught.value is failure
    assert len(opened) == 1 and opened[0].closed


def test_busy_after_wal_setup_is_not_retried(connection_owner, monkeypatch):
    failure = _sqlite_error(sqlite3.SQLITE_BUSY)
    opened, _ = _observe_connections(monkeypatch, [failure], fail_sql="PRAGMA busy_timeout=5000")
    with pytest.raises(sqlite3.OperationalError) as caught:
        connection_owner._open_connection()
    assert caught.value is failure
    assert len(opened) == 1 and opened[0].closed


def test_wal_retry_exhausts_one_shared_timeout_budget(connection_owner, monkeypatch):
    from backend.app import sqlite_connections

    failure = _sqlite_error(sqlite3.SQLITE_BUSY)
    opened, timeouts = _observe_connections(monkeypatch, [failure, failure, failure])
    clock = iter([0.0, 0.0, 1.0, 2.0, 30.0])
    monkeypatch.setattr(sqlite_connections.time, "monotonic", lambda: next(clock))
    sleeps = []
    monkeypatch.setattr(sqlite_connections.time, "sleep", sleeps.append)
    with pytest.raises(sqlite3.OperationalError) as caught:
        connection_owner._open_connection()
    assert caught.value is failure
    assert len(opened) == 2 and all(connection.closed for connection in opened)
    assert timeouts == [30.0, 28.0]
    assert sleeps == [0.01]


def test_expired_retry_budget_does_not_open_another_connection(connection_owner, monkeypatch):
    from backend.app import sqlite_connections

    failure = _sqlite_error(sqlite3.SQLITE_BUSY)
    opened, timeouts = _observe_connections(monkeypatch, [failure, None])
    clock = iter([0.0, 0.0, 29.995, 30.0])
    monkeypatch.setattr(sqlite_connections.time, "monotonic", lambda: next(clock))
    sleeps = []
    monkeypatch.setattr(sqlite_connections.time, "sleep", sleeps.append)
    with pytest.raises(sqlite3.OperationalError) as caught:
        connection_owner._open_connection()
    assert caught.value is failure
    assert len(opened) == 1 and opened[0].closed
    assert timeouts == [30.0]
    assert sleeps == [pytest.approx(0.005)]


@pytest.mark.integration
def test_cold_wal_connections_open_concurrently_without_leaks(connection_owner):
    from concurrent.futures import ThreadPoolExecutor
    import threading

    for _ in range(3):
        connection_owner.db_path.unlink(missing_ok=True)
        barrier = threading.Barrier(6)

        def connect_together(barrier):
            barrier.wait(timeout=10)
            connection = connection_owner._open_connection()
            try:
                return connection.execute("PRAGMA journal_mode").fetchone()[0]
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(connect_together, barrier) for _ in range(6)]
            assert [future.result(timeout=35) for future in futures] == ["wal"] * 6
        with closing(sqlite3.connect(connection_owner.db_path)) as inspector:
            assert inspector.execute("PRAGMA integrity_check").fetchone() == ("ok",)
