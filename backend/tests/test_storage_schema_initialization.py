"""Real SQLite migration races; pipes order the reads, not synthetic schemas."""
from __future__ import annotations

import multiprocessing
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.app.storage import Storage


def _legacy_store(root: Path) -> Path:
    storage = Storage(root)
    path = storage.db_path
    storage.close()
    with sqlite3.connect(path) as db:
        db.execute("ALTER TABLE matches DROP COLUMN analytical_generation_id")
        db.execute("ALTER TABLE matches DROP COLUMN semantic_config_revision")
        db.execute("CREATE TABLE preserved (value TEXT NOT NULL)")
        db.execute("INSERT INTO preserved VALUES ('original')")
    return path


class _PausedSchema:
    def __init__(self, cursor, pipe):
        self.cursor, self.pipe = cursor, pipe

    def fetchall(self):
        rows = self.cursor.fetchall()
        self.pipe.send("snapshot")
        assert self.pipe.poll(20), "schema reader was not released"
        assert self.pipe.recv() == "continue"
        return rows


class _ObservedConnection:
    def __init__(self, connection, pipe):
        self.connection, self.pipe = connection, pipe
        self.paused = False

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def execute(self, sql, *args):
        cursor = self.connection.execute(sql, *args)
        if not self.paused and sql == "PRAGMA table_info(matches)":
            self.paused = True
            return _PausedSchema(cursor, self.pipe)
        return cursor


def _initialize_child(root: str, pipe, second: bool) -> None:
    original = Storage._open_connection

    def observe(storage):
        connection = original(storage)
        if second:
            # SQLite traces BEGIN before trying to acquire its write lock.
            connection.set_trace_callback(
                lambda sql: pipe.send("write-intent")
                if sql.strip().rstrip(";").upper() == "BEGIN IMMEDIATE" else None
            )
        return _ObservedConnection(connection, pipe)

    try:
        with patch.object(Storage, "_open_connection", observe):
            storage = Storage(Path(root))
            storage.close()
        pipe.send(("ok",))
    except Exception as exc:
        pipe.send(("error", type(exc).__name__, str(exc)))
    finally:
        pipe.close()


def _receive(pipe):
    assert pipe.poll(20), "initializer did not reach its expected boundary"
    return pipe.recv()


@pytest.mark.integration
def test_concurrent_schema_initializers_do_not_reuse_stale_columns(tmp_path):
    root = tmp_path / "store"
    path = _legacy_store(root)
    context = multiprocessing.get_context("spawn")
    first, first_child = context.Pipe()
    second, second_child = context.Pipe()
    processes = [
        context.Process(target=_initialize_child, args=(str(root), first_child, False)),
        context.Process(target=_initialize_child, args=(str(root), second_child, True)),
    ]
    started = []
    try:
        processes[0].start(); started.append(processes[0]); first_child.close()
        assert _receive(first) == "snapshot"
        processes[1].start(); started.append(processes[1]); second_child.close()
        boundary = _receive(second)
        assert boundary in {"write-intent", "snapshot"}
        first.send("continue")
        if boundary == "write-intent":
            # The second read now follows the first migration commit. Release it
            # before waiting for unrelated ledger startup writes in the first.
            assert _receive(second) == "snapshot"
            second.send("continue")
            assert _receive(first) == ("ok",)
        else:
            assert _receive(first) == ("ok",)
            second.send("continue")
        assert _receive(second) == ("ok",)
    finally:
        for process in started:
            process.join(5)
            if process.is_alive():
                process.kill(); process.join(5)
        for pipe in (first, first_child, second, second_child):
            pipe.close()
    assert all(process.exitcode == 0 for process in processes)
    with sqlite3.connect(path) as db:
        columns = [row[1] for row in db.execute("PRAGMA table_info(matches)")]
        assert columns.count("analytical_generation_id") == 1
        assert columns.count("semantic_config_revision") == 1
        assert db.execute("SELECT value FROM preserved").fetchall() == [("original",)]
        assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    Storage(root).close()  # Repeated initialization remains idempotent.


def test_failed_schema_migration_rolls_back_before_retry(tmp_path, monkeypatch):
    root = tmp_path / "store"
    path = _legacy_store(root)
    original = Storage._open_connection

    class FailSecondAlter:
        def __init__(self, connection):
            self.connection = connection

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def execute(self, sql, *args):
            if sql == "ALTER TABLE matches ADD COLUMN semantic_config_revision TEXT":
                raise sqlite3.OperationalError("injected second migration failure")
            return self.connection.execute(sql, *args)

    with monkeypatch.context() as scoped:
        scoped.setattr(Storage, "_open_connection", lambda self: FailSecondAlter(original(self)))
        with pytest.raises(sqlite3.OperationalError, match="injected second"):
            Storage(root)
    with sqlite3.connect(path) as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(matches)")}
        assert "analytical_generation_id" not in columns
        assert "semantic_config_revision" not in columns
        assert db.execute("SELECT value FROM preserved").fetchall() == [("original",)]
    Storage(root).close()
    with sqlite3.connect(path) as db:
        assert {"analytical_generation_id", "semantic_config_revision"} <= {
            row[1] for row in db.execute("PRAGMA table_info(matches)")
        }
