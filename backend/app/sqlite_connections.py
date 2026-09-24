"""Shared WAL connection setup; retry only transient journal-mode contention."""
from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
import sqlite3
import time


def open_wal_connection(db_path: Path, *, foreign_keys: bool = False) -> sqlite3.Connection:
    # SQLite may return BUSY without invoking its busy handler (for example while
    # another process closes the last WAL connection). A fresh connection releases
    # any read lock from the failed mode change before retrying. Never retry a
    # transaction, or silently extend the original 30-second connection budget.
    deadline = time.monotonic() + 30.0
    last_busy: sqlite3.OperationalError | None = None
    while True:
        remaining = deadline - time.monotonic()
        if last_busy is not None and remaining <= 0:
            raise last_busy
        with ExitStack() as cleanup:
            connection = sqlite3.connect(
                str(db_path), check_same_thread=False,
                timeout=max(0.0, remaining),
            )
            cleanup.callback(connection.close)
            connection.row_factory = sqlite3.Row
            try:
                connection.execute("PRAGMA journal_mode=WAL")
            except sqlite3.OperationalError as exc:
                code = getattr(exc, "sqlite_errorcode", None)
                remaining = deadline - time.monotonic()
                if not isinstance(code, int) or code & 0xFF != sqlite3.SQLITE_BUSY or remaining <= 0:
                    raise
                last_busy = exc
            else:
                connection.execute("PRAGMA busy_timeout=5000")
                if foreign_keys:
                    connection.execute("PRAGMA foreign_keys=ON")
                cleanup.pop_all()  # Ownership transfers to the caller only on success.
                return connection
        time.sleep(min(0.01, remaining))
