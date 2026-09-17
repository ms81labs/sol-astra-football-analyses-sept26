from __future__ import annotations

import json
from contextlib import contextmanager
import hashlib
import os
import shutil
import sqlite3
import stat
import tempfile
import threading
import uuid
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, TextIO

from pydantic import ValidationError

from .schemas import (
    BallOwnership,
    ColorClusterSummary,
    CreateAnnotationRequest,
    CreateIssueRequest,
    DetectedEvent,
    FormationSegment,
    FrameData,
    JobRecord,
    MatchConfig,
    MatchRecord,
    MatchSummary,
    MatchIssueRecord,
    ReviewBundle,
    ShotAnalytics,
    TacticalAnnotationRecord,
)


_REMOTE_RESULT_FILENAMES = (
    "accepted_match_state.json",
    "analytics.json",
    "ball_pipeline_trace.json",
    "ball_truth_layers.json",
    "decode_anchors.json",
    "events.json",
    "four_rates.json",
    "tactical_report.json",
    "drills.json",
    "frames.json",
    "input_video_identity.json",
    "ownership_publication.json",
    "raw_rows.json",
    "recovery_debug.json",
    "recovery_profile_matrix.json",
)
_COPY_CHUNK_BYTES = 64 * 1024
_UPLOAD_CHUNK_BYTES = 1024 * 1024


class UploadTooLargeError(ValueError):
    pass


class AdmissionOutcomeUncertainError(RuntimeError):
    pass


class ReviewBundleCorruptError(RuntimeError):
    pass


class StorageWriteOutcomeUncertain(OSError):
    pass


class StorageDeleteOutcomeUncertain(OSError):
    pass


def _open_regular_file(path: Path, flags: int = os.O_RDONLY) -> int:
    descriptor = -1
    try:
        descriptor = os.open(
            path,
            flags
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
            0o600,
        )
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError
        return descriptor
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        raise


def _copy_to_snapshot(source: Path, destination: Path) -> tuple[int, tuple[int, int, int]]:
    source_fd = snapshot_fd = -1
    try:
        source_fd = _open_regular_file(source)
        before = os.fstat(source_fd)
        snapshot_fd = _open_regular_file(
            destination,
            os.O_RDWR | os.O_CREAT | os.O_EXCL,
        )
        copied = 0
        while chunk := os.read(source_fd, _COPY_CHUNK_BYTES):
            copied += len(chunk)
            view = memoryview(chunk)
            while view:
                written = os.write(snapshot_fd, view)
                if written <= 0:
                    raise OSError
                view = view[written:]
        after = os.fstat(source_fd)
        named = os.stat(source, follow_symlinks=False)
        identity = (before.st_dev, before.st_ino, before.st_size)
        if (
            not stat.S_ISREG(named.st_mode)
            or (after.st_dev, after.st_ino, after.st_size) != identity
            or (named.st_dev, named.st_ino, named.st_size) != identity
            or copied != before.st_size
        ):
            raise OSError
        os.fsync(snapshot_fd)
        snapshot = os.fstat(snapshot_fd)
        return snapshot_fd, (snapshot.st_dev, snapshot.st_ino, snapshot.st_size)
    except Exception:
        if snapshot_fd >= 0:
            os.close(snapshot_fd)
        destination.unlink(missing_ok=True)
        raise
    finally:
        if source_fd >= 0:
            os.close(source_fd)


def _restore_snapshot(
    source: Path,
    source_fd: int,
    identity: tuple[int, int, int],
    destination: Path,
) -> None:
    opened = os.fstat(source_fd)
    if (
        not stat.S_ISREG(opened.st_mode)
        or (opened.st_dev, opened.st_ino, opened.st_size) != identity
    ):
        raise OSError
    try:
        named = os.stat(source, follow_symlinks=False)
        if (
            stat.S_ISREG(named.st_mode)
            and (named.st_dev, named.st_ino, named.st_size) == identity
        ):
            os.replace(source, destination)
            restored = os.stat(destination, follow_symlinks=False)
            if (
                stat.S_ISREG(restored.st_mode)
                and (restored.st_dev, restored.st_ino, restored.st_size) == identity
            ):
                return
    except OSError:
        pass

    temporary_fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.remote-restore-",
        dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        os.lseek(source_fd, 0, os.SEEK_SET)
        copied = 0
        while chunk := os.read(source_fd, _COPY_CHUNK_BYTES):
            copied += len(chunk)
            view = memoryview(chunk)
            while view:
                written = os.write(temporary_fd, view)
                if written <= 0:
                    raise OSError
                view = view[written:]
        after = os.fstat(source_fd)
        if (
            not stat.S_ISREG(after.st_mode)
            or (after.st_dev, after.st_ino, after.st_size) != identity
            or copied != identity[2]
        ):
            raise OSError
        os.fsync(temporary_fd)
        temporary_identity = os.fstat(temporary_fd)
        os.close(temporary_fd)
        temporary_fd = -1
        os.replace(temporary, destination)
        restored = os.stat(destination, follow_symlinks=False)
        if (
            not stat.S_ISREG(restored.st_mode)
            or (restored.st_dev, restored.st_ino, restored.st_size)
            != (
                temporary_identity.st_dev,
                temporary_identity.st_ino,
                temporary_identity.st_size,
            )
        ):
            raise OSError
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    finally:
        if temporary_fd >= 0:
            os.close(temporary_fd)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _ClosingConnection:
    """sqlite3 connections do not close on context exit; this wrapper does."""

    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection
        self._closed = False

    def __getattr__(self, name: str):
        return getattr(self._connection, name)

    def __enter__(self) -> "_ClosingConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        try:
            if exc_type is None:
                self._connection.commit()
            else:
                try:
                    self._connection.rollback()
                except Exception:
                    pass
        finally:
            self.close()
        return False

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._connection.close()


class Storage:
    def __init__(self, storage_root: Path):
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.storage_root / "guerilla.sqlite3"
        # ponytail: per-instance only; use a cross-process lock if multiple Storage instances mutate these files.
        self._annotation_issue_lock = threading.Lock()
        # ponytail: per-instance only; use a cross-process lock if multiple API workers mutate bundles.
        self._review_bundle_lock = threading.Lock()
        # ponytail: per-instance config serialization; use per-match cross-process locks for multiple API workers.
        self.config_update_lock = threading.Lock()
        self._initialize()
        from .workbench.jobs import DurableJobLedger

        self.job_ledger = DurableJobLedger(db_path=self.db_path)

    def close(self) -> None:
        try:
            connection = self._open_connection()
            try:
                connection.execute("PRAGMA wal_checkpoint(PASSIVE)")
            finally:
                connection.close()
        except Exception:
            pass
        ledger = getattr(self, "job_ledger", None)
        if ledger is not None and hasattr(ledger, "close"):
            ledger.close()

    def _open_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _connect(self) -> _ClosingConnection:
        return _ClosingConnection(self._open_connection())

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS matches (
                    id TEXT PRIMARY KEY,
                    admission_token TEXT,
                    name TEXT NOT NULL,
                    input_mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    input_path TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    analytics_summary_json TEXT,
                    requires_team_selection INTEGER NOT NULL DEFAULT 0,
                    team_clusters_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    match_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress REAL NOT NULL,
                    message TEXT,
                    error TEXT,
                    runpod_run_id TEXT,
                    log_path TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(match_id) REFERENCES matches(id)
                );
                """
            )
            match_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(matches)").fetchall()
            }
            if "admission_token" not in match_columns:
                connection.execute("ALTER TABLE matches ADD COLUMN admission_token TEXT")
            if "analytics_summary_json" not in match_columns:
                connection.execute("ALTER TABLE matches ADD COLUMN analytics_summary_json TEXT")
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS matches_admission_token_unique "
                "ON matches(admission_token) WHERE admission_token IS NOT NULL"
            )
            job_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
            }
            if "log_path" not in job_columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN log_path TEXT")
            if "runpod_run_id" not in job_columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN runpod_run_id TEXT")
            if "started_at" not in job_columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN started_at TEXT")
            if "completed_at" not in job_columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN completed_at TEXT")

    def _match_dir(self, match_id: str) -> Path:
        path = self.storage_root / "matches" / match_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    @contextmanager
    def remote_result_import(self, match_id: str) -> Iterator[None]:
        """Restore owned football outputs and match metadata if import fails."""

        match_dir = self._match_dir(match_id)
        with self._connect() as connection:
            match_row = connection.execute(
                "SELECT status, config_json, requires_team_selection, team_clusters_json, updated_at "
                "FROM matches WHERE id = ?",
                (match_id,),
            ).fetchone()
        if match_row is None:
            raise KeyError(match_id)

        temporary = Path(tempfile.mkdtemp(prefix=".remote-import-", dir=self.storage_root))
        snapshot = temporary / "snapshot"
        snapshot.mkdir()
        snapshots: dict[str, tuple[int, tuple[int, int, int]]] = {}

        def cleanup_temporary() -> None:
            try:
                shutil.rmtree(temporary)
                if temporary.exists():
                    raise OSError
            except Exception:
                raise RuntimeError(
                    "remote result rollback cleanup could not be confirmed"
                ) from None

        def restore() -> None:
            try:
                for filename in _REMOTE_RESULT_FILENAMES:
                    destination = match_dir / filename
                    retained = snapshots.get(filename)
                    if retained is not None:
                        _restore_snapshot(
                            snapshot / filename,
                            retained[0],
                            retained[1],
                            destination,
                        )
                    else:
                        destination.unlink(missing_ok=True)
                with self._connect() as connection:
                    connection.execute(
                        """
                        UPDATE matches
                        SET status = ?, config_json = ?, requires_team_selection = ?, team_clusters_json = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            match_row["status"],
                            match_row["config_json"],
                            match_row["requires_team_selection"],
                            match_row["team_clusters_json"],
                            match_row["updated_at"],
                            match_id,
                        ),
                    )
            except Exception:
                raise RuntimeError(
                    "remote result rollback could not be confirmed"
                ) from None

        try:
            try:
                for filename in _REMOTE_RESULT_FILENAMES:
                    source = match_dir / filename
                    try:
                        source.lstat()
                    except FileNotFoundError:
                        continue
                    snapshots[filename] = _copy_to_snapshot(
                        source, snapshot / filename
                    )
            except Exception:
                cleanup_temporary()
                raise RuntimeError(
                    "remote result snapshot could not be confirmed"
                ) from None
            try:
                yield
            except BaseException:
                restore()
                cleanup_temporary()
                raise
            try:
                cleanup_temporary()
            except Exception:
                restore()
                raise
        finally:
            for descriptor, _identity in snapshots.values():
                os.close(descriptor)

    def save_upload(self, filename: str, payload: bytes) -> Path:
        return self.save_upload_stream(filename, BytesIO(payload))

    def save_upload_stream(
        self,
        filename: str,
        stream: BinaryIO,
        max_bytes: int | None = None,
    ) -> Path:
        if max_bytes is not None and (type(max_bytes) is not int or max_bytes <= 0):
            raise ValueError("max_bytes must be a positive integer")
        upload_dir = self.storage_root / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        path = upload_dir / f"{uuid.uuid4().hex}_{Path(filename).name or 'upload.bin'}"
        temporary_fd, temporary_name = tempfile.mkstemp(prefix=".upload.", dir=upload_dir)
        temporary = Path(temporary_name)
        published = False
        try:
            handle = os.fdopen(temporary_fd, "wb")
            temporary_fd = -1
            with handle:
                total = 0
                while chunk := stream.read(_UPLOAD_CHUNK_BYTES):
                    total += len(chunk)
                    if max_bytes is not None and total > max_bytes:
                        raise UploadTooLargeError(
                            f"Upload exceeds maximum size of {max_bytes} bytes"
                        )
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            published = True
            directory_fd = os.open(
                upload_dir,
                os.O_RDONLY
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            return path
        except BaseException:
            if temporary_fd >= 0:
                try:
                    os.close(temporary_fd)
                except OSError:
                    pass
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            if published:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise

    def create_match(self, name: str, input_mode: str, original_filename: str, input_path: Path, config: MatchConfig) -> MatchRecord:
        match_id = uuid.uuid4().hex
        now = _utcnow().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO matches (id, name, input_mode, status, original_filename, input_path, config_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    name,
                    input_mode,
                    "processing",
                    original_filename,
                    str(input_path),
                    config.model_dump_json(),
                    now,
                    now,
                ),
            )
        return self.get_match(match_id)

    def create_job(self, match_id: str) -> JobRecord:
        job, _created = self.ensure_job(match_id, uuid.uuid4().hex, created_status="queued")
        return job

    def ensure_job(
        self,
        match_id: str,
        job_id: str,
        *,
        created_status: str = "queued",
        budget: float = 0.0,
        namespace: str = "production",
    ) -> tuple[JobRecord, bool]:
        self.get_match(match_id)
        try:
            existing = self.get_job(job_id)
        except KeyError:
            existing = None
        if existing is not None:
            if existing.matchId != match_id:
                raise ValueError("job belongs to another match")
            return existing, False
        now = _utcnow().isoformat()
        log_path = str(self.storage_root / "logs" / f"job_{job_id}.log")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (id, match_id, status, progress, message, error, log_path, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, match_id, created_status, 0.0, "Queued", None, log_path, now, now),
            )
        self._admit_durable_job(match_id, job_id, budget=budget, namespace=namespace)
        return self.get_job(job_id), True

    def _admit_durable_job(
        self,
        match_id: str,
        job_id: str,
        *,
        budget: float = 0.0,
        namespace: str = "production",
    ) -> None:
        from .workbench.jobs import JobRequest

        if job_id in self.job_ledger.requests:
            return
        try:
            sha = self.source_sha256(match_id)
        except Exception:
            sha = "0" * 64
        self.job_ledger.submit(
            JobRequest(
                requestId=job_id,
                matchId=match_id,
                sourceSha256=sha or "0" * 64,
                intervalStart=0.0,
                intervalEnd=0.0,
                temporalPolicy="source_global_grid",
                decoderVersion="opencv",
                modelHash="unspecified",
                outputSchema="evidence_v1",
                budget=float(budget),
                authorisedLocation="local",
                namespace=namespace,  # type: ignore[arg-type]
            )
        )

    def source_sha256(self, match_id: str) -> str:
        path = self.get_match_input_path(match_id)
        if not path.exists() or not path.is_file():
            return "0" * 64
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(_COPY_CHUNK_BYTES), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def has_active_job(self, match_id: str) -> bool:
        with self._connect() as connection:
            return connection.execute(
                "SELECT 1 FROM jobs WHERE match_id = ? "
                "AND status IN ('dispatching', 'queued', 'processing') LIMIT 1",
                (match_id,),
            ).fetchone() is not None

    def get_admission_by_token(
        self,
        admission_token: str,
    ) -> tuple[MatchRecord, JobRecord] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT matches.id AS match_id, jobs.id AS job_id
                FROM matches JOIN jobs ON jobs.match_id = matches.id
                WHERE matches.admission_token = ?
                ORDER BY jobs.created_at, jobs.id
                LIMIT 1
                """,
                (admission_token,),
            ).fetchone()
        if row is None:
            return None
        return self.get_match(row["match_id"]), self.get_job(row["job_id"])

    def _discard_upload(self, path: Path) -> None:
        upload_dir = self.storage_root / "uploads"
        candidate = Path(path)
        if candidate.absolute().parent != upload_dir.absolute() or candidate.name in {"", ".", ".."}:
            raise RuntimeError("upload cleanup target is outside owned upload storage")
        directory_fd = os.open(
            upload_dir,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            try:
                target = os.stat(candidate.name, dir_fd=directory_fd, follow_symlinks=False)
            except FileNotFoundError:
                return
            if not stat.S_ISREG(target.st_mode):
                raise RuntimeError("upload cleanup target is not a regular file")
            os.unlink(candidate.name, dir_fd=directory_fd)
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

    def admit_match_job(
        self,
        *,
        match_id: str,
        job_id: str,
        admission_token: str,
        name: str,
        input_mode: str,
        original_filename: str,
        input_path: Path,
        config: MatchConfig,
    ) -> tuple[MatchRecord, JobRecord, bool]:
        now = _utcnow().isoformat()
        log_path = str(self.storage_root / "logs" / f"job_{job_id}.log")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT matches.id AS match_id, jobs.id AS job_id
                FROM matches JOIN jobs ON jobs.match_id = matches.id
                WHERE matches.admission_token = ?
                ORDER BY jobs.created_at, jobs.id
                LIMIT 1
                """,
                (admission_token,),
            ).fetchone()
            if existing is not None:
                connection.rollback()
                connection.close()
                self._discard_upload(input_path)
                return (
                    self.get_match(existing["match_id"]),
                    self.get_job(existing["job_id"]),
                    False,
                )
            connection.execute(
                """
                INSERT INTO matches (
                    id, admission_token, name, input_mode, status, original_filename,
                    input_path, config_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    admission_token,
                    name,
                    input_mode,
                    "processing",
                    original_filename,
                    str(input_path),
                    config.model_dump_json(),
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO jobs (
                    id, match_id, status, progress, message, error, log_path,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    match_id,
                    "dispatching",
                    0.0,
                    "Dispatching",
                    None,
                    log_path,
                    now,
                    now,
                ),
            )
            connection.commit()
        except BaseException as error:
            try:
                connection.rollback()
            except Exception:
                pass
            try:
                connection.close()
            except Exception:
                pass
            try:
                admitted = self.get_admission_by_token(admission_token)
            except Exception:
                raise AdmissionOutcomeUncertainError(
                    "match admission commit outcome could not be confirmed"
                ) from error
            if admitted is not None:
                created = admitted[0].id == match_id
                if not created:
                    self._discard_upload(input_path)
                return admitted[0], admitted[1], created
            self._discard_upload(input_path)
            raise
        else:
            try:
                connection.close()
            except Exception:
                pass
        try:
            return self.get_match(match_id), self.get_job(job_id), True
        except Exception as error:
            raise AdmissionOutcomeUncertainError(
                "committed match admission could not be read"
            ) from error

    def mark_dispatched(self, job_id: str) -> JobRecord:
        now = _utcnow().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = 'queued', message = 'Queued', updated_at = ?
                WHERE id = ? AND status = 'dispatching'
                """,
                (now, job_id),
            )
        return self.get_job(job_id)

    def mark_dispatch_failed(
        self,
        match_id: str,
        job_id: str,
        *,
        error: str,
    ) -> JobRecord:
        now = _utcnow().isoformat()
        with self._connect() as connection:
            updated = connection.execute(
                """
                UPDATE jobs
                SET status = 'failed', message = ?, error = ?,
                    started_at = COALESCE(started_at, ?), completed_at = ?, updated_at = ?
                WHERE id = ? AND status IN ('dispatching', 'queued', 'processing')
                """,
                (error, error, now, now, now, job_id),
            )
            if updated.rowcount:
                connection.execute(
                    "UPDATE matches SET status = 'failed', updated_at = ? WHERE id = ?",
                    (now, match_id),
                )
        return self.get_job(job_id)

    def update_job(
        self,
        job_id: str,
        *,
        status: str,
        progress: float,
        message: str | None = None,
        error: str | None = None,
        remote_run_id: str | None = None,
    ) -> JobRecord:
        now = _utcnow().isoformat()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT started_at, completed_at, runpod_run_id FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                raise KeyError(job_id)

            started_at = row["started_at"]
            completed_at = row["completed_at"]
            persisted_remote_run_id = remote_run_id if remote_run_id is not None else row["runpod_run_id"]
            if status == "processing" and started_at is None:
                started_at = now
            if status in {"completed", "failed"}:
                if started_at is None:
                    started_at = now
                completed_at = now

            connection.execute(
                """
                UPDATE jobs
                SET status = ?, progress = ?, message = ?, error = ?, runpod_run_id = ?, started_at = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, progress, message, error, persisted_remote_run_id, started_at, completed_at, now, job_id),
            )
        record = self.get_job(job_id)
        ledger = getattr(self, "job_ledger", None)
        mapped = {"completed": "complete", "complete": "complete", "failed": "failed"}.get(status)
        if ledger is not None and mapped and job_id in getattr(ledger, "requests", {}):
            try:
                ledger.transition(job_id, mapped)
            except Exception:
                pass
        return record

    def update_match_status(
        self,
        match_id: str,
        *,
        status: str,
        requires_team_selection: bool = False,
        team_clusters: list[ColorClusterSummary] | None = None,
    ) -> MatchRecord:
        now = _utcnow().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE matches SET status = ?, requires_team_selection = ?, team_clusters_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    int(requires_team_selection),
                    json.dumps([cluster.model_dump(mode="json") for cluster in (team_clusters or [])]),
                    now,
                    match_id,
                ),
            )
        return self.get_match(match_id)

    def update_match_config(self, match_id: str, config: MatchConfig) -> MatchRecord:
        now = _utcnow().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE matches SET config_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (config.model_dump_json(), now, match_id),
            )
        return self.get_match(match_id)

    def get_job(self, job_id: str) -> JobRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        started_at = datetime.fromisoformat(row["started_at"]) if row["started_at"] else None
        completed_at = datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
        duration_seconds = None
        if started_at is not None and completed_at is not None:
            duration_seconds = max(0.0, (completed_at - started_at).total_seconds())
        return JobRecord(
            id=row["id"],
            matchId=row["match_id"],
            status=row["status"],
            progress=row["progress"],
            message=row["message"],
            error=row["error"],
            remoteRunId=row["runpod_run_id"],
            logPath=row["log_path"] or str(self.storage_root / "logs" / f"job_{row['id']}.log"),
            startedAt=started_at,
            completedAt=completed_at,
            durationSeconds=duration_seconds,
            createdAt=datetime.fromisoformat(row["created_at"]),
            updatedAt=datetime.fromisoformat(row["updated_at"]),
        )

    def get_match(self, match_id: str) -> MatchRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
        if row is None:
            raise KeyError(match_id)
        team_clusters = json.loads(row["team_clusters_json"] or "[]")
        return MatchRecord(
            id=row["id"],
            name=row["name"],
            inputMode=row["input_mode"],
            status=row["status"],
            originalFilename=row["original_filename"],
            config=MatchConfig.model_validate_json(row["config_json"]),
            createdAt=datetime.fromisoformat(row["created_at"]),
            updatedAt=datetime.fromisoformat(row["updated_at"]),
            requiresTeamSelection=bool(row["requires_team_selection"]),
            teamClusters=[ColorClusterSummary.model_validate(item) for item in team_clusters],
        )

    def get_match_input_path(self, match_id: str) -> Path:
        with self._connect() as connection:
            row = connection.execute("SELECT input_path FROM matches WHERE id = ?", (match_id,)).fetchone()
        if row is None:
            raise KeyError(match_id)
        return Path(row["input_path"])

    def list_matches(self) -> list[MatchRecord]:
        with self._connect() as connection:
            rows = connection.execute("SELECT id FROM matches ORDER BY created_at DESC").fetchall()
        return [self.get_match(row["id"]) for row in rows]

    def save_frames(self, match_id: str, frames: Iterable[FrameData]) -> None:
        self._write_json_array(self._match_dir(match_id) / "frames.json", (frame.model_dump(mode="json") for frame in frames))

    def save_raw_rows(self, match_id: str, rows: Iterable[dict]) -> None:
        self._write_json_array(self._match_dir(match_id) / "raw_rows.json", rows)

    def _video_ball_signal_summary(self, match_id: str, summary: MatchSummary) -> MatchSummary:
        # ponytail: promote video trust only after a match-bound independent ball-label receipt exists.
        try:
            match = self.get_match(match_id)
        except KeyError:
            return summary  # Artifact-only records have no authoritative input mode.
        if match.inputMode == "video" and summary.ballSignalStatus == "trusted":
            return summary.model_copy(update={
                "ballSignalStatus": "untrusted",
                "ballSignalMessage": "Ball detections have not been independently verified.",
            })
        return summary

    def save_analytics(
        self,
        match_id: str,
        summary: MatchSummary,
        assignments: list[BallOwnership],
        formation_timeline: list[FormationSegment],
        shots: list[ShotAnalytics],
    ) -> None:
        summary = self._video_ball_signal_summary(match_id, summary)
        if not any(assignment.team in {"my_team", "enemy"} for assignment in assignments):
            summary = summary.model_copy(update={"possession": None})
        self._write_json(
            self._match_dir(match_id) / "analytics.json",
            {
                "summary": summary.model_dump(mode="json"),
                "ballAssignments": [assignment.model_dump(mode="json") for assignment in assignments],
                "formationTimeline": [segment.model_dump(mode="json") for segment in formation_timeline],
                "shots": [shot.model_dump(mode="json") for shot in shots],
            },
        )
        with self._connect() as connection:
            connection.execute(
                "UPDATE matches SET analytics_summary_json = ? WHERE id = ?",
                (summary.model_dump_json(), match_id),
            )

    def save_events(self, match_id: str, events: list[DetectedEvent]) -> None:
        self._write_json(self._match_dir(match_id) / "events.json", [event.model_dump(mode="json") for event in events])

    def save_analysis_artifact(self, match_id: str, analysis_type: str, payload: dict) -> None:
        path = self._match_dir(match_id) / f"{analysis_type}.json"
        if analysis_type.endswith(".receipt") or analysis_type in {"worker_progress", "remote_worker_progress"}:
            self._write_json(path, payload)
            return
        previous = path.read_bytes() if path.exists() else b""
        previous_digest = hashlib.sha256(previous).hexdigest() if previous else "0" * 64
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        from .workbench.artifacts import ArtifactStore, write_alongside

        receipt = write_alongside(
            ArtifactStore(self.storage_root / "artifacts"),
            previous_digest=previous_digest,
            payload=encoded,
            namespace=analysis_type,
        )
        self._write_json(path, payload)
        receipt_path = self._match_dir(match_id) / "receipts" / f"{analysis_type}.json"
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json(receipt_path, receipt)

    def invalidate_coach_analysis(self, match_id: str) -> None:
        for analysis_type in ("tactical_report", "drills"):
            (self._match_dir(match_id) / f"{analysis_type}.json").unlink(missing_ok=True)

    def append_analysis_artifact_jsonl(self, match_id: str, analysis_type: str, payload: dict) -> None:
        path = self._match_dir(match_id) / f"{analysis_type}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":")))
            handle.write("\n")

    def load_frames(self, match_id: str) -> list[FrameData]:
        payload = self._read_json(self._match_dir(match_id) / "frames.json")
        return [FrameData.model_validate(item) for item in payload]

    def load_frames_page(
        self,
        match_id: str,
        *,
        after_frame: int | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> dict:
        from .workbench.repository import RepositoryAdapter

        return RepositoryAdapter().page_frames(
            self.load_frames(match_id),
            after_frame=after_frame,
            cursor=cursor,
            limit=limit,
        )

    def load_evidence_page(
        self,
        match_id: str,
        *,
        interval_start: float | None = None,
        interval_end: float | None = None,
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict:
        from .workbench.evidence import query_match_evidence

        frames = self.load_frames(match_id)
        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            events = []
        page = query_match_evidence(
            frames,
            events,
            interval_start=interval_start,
            interval_end=interval_end,
            cursor=cursor,
            limit=limit,
            match_id=match_id,
        )
        return page.model_dump(mode="json")

    def _corrections_path(self, match_id: str) -> Path:
        self.get_match(match_id)
        path = self._match_dir(match_id) / "corrections.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _load_correction_log(self, match_id: str):
        from .workbench.review import CorrectionLog

        path = self._corrections_path(match_id)
        if not path.exists():
            return CorrectionLog()
        return CorrectionLog.from_payload(self._read_json(path))

    def _save_correction_log(self, match_id: str, log) -> None:
        self._write_json(self._corrections_path(match_id), log.dump())

    def submit_correction(
        self,
        match_id: str,
        *,
        kind: str,
        payload: dict | None = None,
        author: str = "analyst",
        expected_version: int | None = None,
        crash_before_commit: bool = False,
    ):
        from .workbench.review import new_correction

        payload = dict(payload or {})
        if kind in {"event_accept", "event_reject"}:
            payload["previous"] = self._event_review_snapshot(match_id, payload)
        with self._annotation_issue_lock:
            log = self._load_correction_log(match_id)
            saved = log.submit(
                new_correction(match_id, kind, payload, author=author),  # type: ignore[arg-type]
                crash_before_commit=crash_before_commit,
                expected_version=expected_version,
            )
            self._save_correction_log(match_id, log)
        if saved.saveState == "saved":
            self._apply_saved_correction(match_id, saved)
        return saved

    def recover_correction(self, match_id: str, correction_id: str):
        with self._annotation_issue_lock:
            log = self._load_correction_log(match_id)
            saved = log.recover(correction_id)
            if saved.matchId != match_id:
                raise KeyError(correction_id)
            self._save_correction_log(match_id, log)
        if saved.saveState == "saved":
            self._apply_saved_correction(match_id, saved)
        return saved

    def undo_correction(self, match_id: str, correction_id: str, *, author: str = "analyst"):
        with self._annotation_issue_lock:
            log = self._load_correction_log(match_id)
            original = next((item for item in log.history(match_id) if item.correctionId == correction_id), None)
            saved = log.undo(correction_id, author=author)
            self._save_correction_log(match_id, log)
        if original is not None and original.kind == "track_split":
            payload = dict(original.payload or {})
            new_track_id = payload.get("newTrackId")
            source = payload.get("trackId")
            if new_track_id is not None and source not in {None, ""}:
                self._apply_identity_edit(
                    match_id,
                    kind="track_split",
                    payload={
                        "trackId": str(new_track_id),
                        "atFrame": int(payload.get("atFrame") or 0),
                        "newTrackId": int(source),
                    },
                )
        elif original is not None and original.kind in {"event_accept", "event_reject"}:
            self._restore_event_review(match_id, list((original.payload or {}).get("previous") or []))
        elif original is not None and original.kind == "team_mapping":
            self._apply_team_mapping(match_id, dict(original.payload or {}))
        elif original is not None and original.kind == "track_join":
            self._apply_identity_edit(match_id, kind="track_join_undo", payload=dict(original.payload or {}))
        elif original is not None and original.kind == "identity_validate":
            self._recompute_identity_continuity(match_id, identity_continuous=False)
        elif original is not None and original.kind == "calibration":
            self._restore_calibration_evaluation(match_id, dict((original.payload or {}).get("previous") or {}))
        return saved

    def list_corrections(self, match_id: str, *, state: str | None = None) -> list[dict]:
        log = self._load_correction_log(match_id)
        items = log.pending(match_id) if state == "pending" else log.history(match_id)
        return [item.model_dump(mode="json") for item in items]

    def _active_playlist_payloads(self, match_id: str) -> list[dict]:
        corrections = self.list_corrections(match_id)
        undone = {
            item.get("undoOf")
            for item in corrections
            if isinstance(item.get("undoOf"), str) and item.get("undoOf")
        }
        payloads: list[dict] = []
        for item in corrections:
            if item.get("kind") != "playlist_item":
                continue
            if item.get("undoOf"):
                continue
            if item.get("correctionId") in undone:
                continue
            if item.get("saveState") != "saved":
                continue
            payload = item.get("payload") or {}
            if isinstance(payload, dict):
                payloads.append(payload)
        return payloads

    def _event_review_snapshot(self, match_id: str, payload: dict) -> list[dict]:
        from .workbench.events import event_matches_review_payload

        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            return []
        previous: list[dict] = []
        for index, event in enumerate(events):
            if not event_matches_review_payload(event, payload, match_id=match_id, index=index):
                continue
            previous.append(
                {
                    "frameId": int(event.frameId),
                    "timestamp": event.timestamp,
                    "type": event.type,
                    "reviewStatus": event.reviewStatus,
                }
            )
        return previous

    def _apply_saved_correction(self, match_id: str, saved) -> None:
        if saved.kind in {"event_accept", "event_reject"}:
            from .workbench.events import apply_event_review

            try:
                events = self.load_events(match_id)
            except FileNotFoundError:
                return
            updated, _previous = apply_event_review(
                events,
                kind=saved.kind,
                payload=dict(saved.payload or {}),
                match_id=match_id,
            )
            self.save_events(match_id, updated)
            return
        if saved.kind == "team_mapping":
            self._apply_team_mapping(match_id, dict(saved.payload or {}))
            return
        if saved.kind == "identity_validate":
            self._recompute_identity_continuity(match_id, identity_continuous=True)
            return
        if saved.kind == "calibration":
            self._save_calibration_evaluation(match_id, dict((saved.payload or {}).get("evaluation") or {}))

    def _apply_team_mapping(self, match_id: str, payload: dict) -> None:
        if payload.get("swap") is not True:
            return
        from .processor import reprocess_video_match
        from .workbench.identity import apply_team_swap

        try:
            frames = self.load_frames(match_id)
        except FileNotFoundError:
            return
        self.save_frames(match_id, apply_team_swap(frames))
        reprocess_video_match(self, match_id)

    def _restore_event_review(self, match_id: str, previous: list[dict]) -> None:
        from .workbench.events import restore_event_review

        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            return
        self.save_events(match_id, restore_event_review(events, previous))

    def query_match_events(self, match_id: str, query_text: str) -> dict:
        from .workbench.assistance import events_as_query_rows, execute_typed_query, parse_typed_query

        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            events = []
        query = parse_typed_query(query_text)
        hits = execute_typed_query(events_as_query_rows(events, match_id=match_id), query, match_id=match_id)
        return {
            "query": query.model_dump(mode="json"),
            "results": [hit.model_dump(mode="json") for hit in hits],
        }

    def assemble_match_report(
        self,
        match_id: str,
        *,
        claimed_evidence_ids: list[str] | None = None,
        narrative: dict | None = None,
    ) -> dict:
        from .workbench.assistance import events_as_query_rows
        from .workbench.evidence import records_from_match, summarize_legacy_match
        from .workbench.reports import assemble_report

        summary, _, _, _ = self.load_analytics(match_id)
        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            events = []
        frames = self.load_frames(match_id)
        records = records_from_match(frames, events)
        known = {record.evidenceId for record in records}
        controlled = sum(
            1
            for frame in frames
            if frame.possession is not None and frame.possession.team in {"my_team", "enemy"}
        )
        metrics = [
            metric.model_dump(mode="json")
            for metric in summarize_legacy_match(
                summary.model_dump(mode="json"),
                identity_continuous=self._stored_identity_continuous(match_id),
                calibration_accepted=self._stored_calibration_accepted(match_id),
                controlled_frames=controlled,
            )
        ]
        event_rows = [
            row
            for row in events_as_query_rows(events, match_id=match_id)
            if row.get("reviewStatus") != "rejected"
        ]
        if claimed_evidence_ids is None:
            claimed = [evidence_id for row in event_rows for evidence_id in row.get("evidenceIds") or []]
        else:
            claimed = list(claimed_evidence_ids)
        return assemble_report(
            metrics=metrics,
            events=event_rows,
            claimed_evidence_ids=claimed,
            known_evidence_ids=known,
            narrative=narrative,
        )

    def player_observations_for_match(self, match_id: str) -> dict:
        from .workbench.identity import player_observations, rows_from_frames

        return player_observations(
            rows_from_frames(self.load_frames(match_id)),
            identity_continuous=self._stored_identity_continuous(match_id),
        )

    def search_stored_library(self, query: str) -> dict:
        from .workbench.library import search_match_library

        matches = [
            {
                "id": match.id,
                "title": match.name,
                "name": match.name,
                "cameraProfile": match.config.cameraProfile,
                "inputMode": match.inputMode,
                "status": match.status,
            }
            for match in self.list_matches()
        ]
        return search_match_library(query=query, matches=matches)

    def classify_match_ownership(self, match_id: str) -> dict:
        from .workbench.ownership import classify_ownership

        frames = self.load_frames(match_id)
        if not frames:
            observation = classify_ownership(
                ball_visible=False,
                nearest_team=None,
                nearest_distance=None,
                relative_motion=None,
                persistence_frames=0,
                calibrated=False,
            )
            return observation.model_dump(mode="json")
        frame = frames[0]
        possession = frame.possession
        nearest_team = None
        nearest_distance = None
        if possession is not None and possession.team in {"my_team", "enemy"}:
            nearest_team = possession.team
            nearest_distance = possession.distance
        observation = classify_ownership(
            ball_visible=frame.ball is not None,
            nearest_team=nearest_team,
            nearest_distance=nearest_distance,
            relative_motion=None,
            persistence_frames=0,
            calibrated=False,
        )
        return observation.model_dump(mode="json")

    def publish_ownership_events(self, match_id: str) -> dict:
        from .workbench.events import propose_event
        from .workbench.ownership import OwnershipHysteresis, classify_ownership

        frames = self.load_frames(match_id)
        hysteresis = OwnershipHysteresis()
        states = []
        for frame in frames:
            possession = frame.possession
            nearest_team = possession.team if possession is not None and possession.team in {"my_team", "enemy"} else None
            if nearest_team is None and frame.myTeam:
                nearest_team = "my_team"
            observation = classify_ownership(
                ball_visible=frame.ball is not None,
                nearest_team=nearest_team,
                nearest_distance=possession.distance if possession is not None else None,
                relative_motion="stable" if nearest_team else None,
                persistence_frames=3 if nearest_team else 0,
                calibrated=False,
            )
            held = hysteresis.observe(observation.controllingTeam if observation.mode == "controlled_possession" else "unknown")
            payload = observation.model_dump(mode="json")
            payload["hysteresisTeam"] = held
            payload["timestamp"] = frame.timestamp
            payload["nearestIsNotControl"] = True
            states.append(payload)
        event = propose_event(family="turnover", release=None, receipt=None)
        published = {
            "nearestIsNotControl": True,
            "states": states,
            "eventsPublication": event.model_dump(mode="json"),
        }
        self.save_analysis_artifact(match_id, "ownership_publication", published)
        return published

    def assemble_stored_match_package(self, match_id: str) -> dict:
        from .workbench.assistance import events_as_query_rows
        from .workbench.evidence import summarize_legacy_match
        from .workbench.package import assemble_match_package

        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            events = []
        frames = self.load_frames(match_id)
        summary, _, _, _ = self.load_analytics(match_id)
        controlled = sum(
            1
            for frame in frames
            if frame.possession is not None and frame.possession.team in {"my_team", "enemy"}
        )
        metrics = [
            metric.model_dump(mode="json")
            for metric in summarize_legacy_match(
                summary.model_dump(mode="json"),
                identity_continuous=self._stored_identity_continuous(match_id),
                calibration_accepted=self._stored_calibration_accepted(match_id),
                controlled_frames=controlled,
            )
        ]
        corrections = self.list_corrections(match_id)
        playlist = self._active_playlist_payloads(match_id)
        return assemble_match_package(
            playlist=playlist,
            events=[
                row
                for row in events_as_query_rows(events, match_id=match_id)
                if row.get("reviewStatus") != "rejected"
            ],
            metrics=metrics,
            corrections=corrections,
            cost={},
            secrets={},
        )

    def incident_geometry_for_match(self, match_id: str) -> dict:
        from .workbench.geometry import review_incident_geometry

        match = self.get_match(match_id)
        frames = self.load_frames(match_id)
        if not frames:
            raise FileNotFoundError(match_id)
        frame = frames[0]
        ball = frame.ball
        return review_incident_geometry(
            my_team=[{"x": float(player.x), "y": float(player.y)} for player in frame.myTeam],
            enemies=[{"x": float(player.x), "y": float(player.y)} for player in frame.enemies],
            ball=None if ball is None else {"x": float(ball.x), "y": float(ball.y)},
            attack_direction=match.config.attackDirection,
        )

    def assess_stored_match_setup(self, match_id: str) -> dict:
        from .workbench.setup import assess_match_setup

        match = self.get_match(match_id)
        config = match.config
        return assess_match_setup(
            camera_profile=config.cameraProfile,
            pitch_length_m=config.pitchLengthM,
            rights=config.rights.model_dump(mode="json"),
            periods=[period.model_dump(mode="json") for period in config.periods],
            home_team=config.homeTeam,
            away_team=config.awayTeam,
            calibration_committed=config.calibrationCommitted,
        )

    def four_rates_for_match(self, match_id: str) -> dict:
        self.get_match(match_id)
        try:
            payload = self.load_analysis_artifact(match_id, "four_rates")
        except FileNotFoundError:
            payload = None
        body = dict(payload or {})
        notes = [str(item) for item in body.get("notes") or []]
        if payload is None:
            notes.append("FOUR_RATES_UNRECORDED")
        if "EXPORT_FPS_IS_NOT_INFERENCE_FPS" not in notes:
            notes.append("EXPORT_FPS_IS_NOT_INFERENCE_FPS")
        return {
            "decodeCount": int(body.get("decodeCount") or 0),
            "detectorPrimaryCount": int(body.get("detectorPrimaryCount") or body.get("inferenceCount") or 0),
            "detectorRecoveryCount": int(body.get("detectorRecoveryCount") or 0),
            "trackerUpdateCount": int(body.get("trackerUpdateCount") or 0),
            "exportCount": int(body.get("exportCount") or 0),
            "exportFpsEqualsInferenceFps": False,
            "decodeFpsEqualsExportFps": False,
            "notes": notes,
        }

    def match_metrics_for_match(self, match_id: str) -> dict:
        from .workbench.evidence import summarize_legacy_match

        summary, _, _, _ = self.load_analytics(match_id)
        try:
            frames = self.load_frames(match_id)
        except FileNotFoundError:
            frames = []
        controlled = sum(
            1
            for frame in frames
            if frame.possession is not None and frame.possession.team in {"my_team", "enemy"}
        )
        metrics = [
            metric.model_dump(mode="json")
            for metric in summarize_legacy_match(
                summary.model_dump(mode="json"),
                identity_continuous=self._stored_identity_continuous(match_id),
                calibration_accepted=self._stored_calibration_accepted(match_id),
                controlled_frames=controlled,
            )
        ]
        return {"metrics": metrics}

    def inspect_match_metric(self, match_id: str, metric: str) -> dict:
        from .workbench.evidence import inspect_metric

        payload = self.match_metrics_for_match(match_id)
        item = next((row for row in payload["metrics"] if row.get("metric") == metric), None)
        if item is None:
            return inspect_metric(metric)
        return inspect_metric(
            metric,
            value=item.get("value"),
            availability=str(item.get("availability") or "unknown"),
            eligible_duration=float(item.get("eligibleSeconds") or 0.0),
            exclusions=list(item.get("reasonCodes") or []),
        )

    def incident_package_for_match(self, match_id: str) -> dict:
        from .workbench.incidents import level0_incident_package

        self.get_match(match_id)
        clips = self._active_playlist_payloads(match_id)
        return level0_incident_package(clips=clips, notes=[], bookmarks=[])

    def clock_for_match(self, match_id: str) -> dict:
        self.get_match(match_id)
        try:
            source_clock = self.load_analysis_artifact(match_id, "source_clock")
        except FileNotFoundError:
            source_clock = None
        try:
            frames = self.load_frames(match_id)
        except FileNotFoundError:
            frames = []
        presentation = float(frames[0].timestamp) if frames else 0.0
        offset = 0.0
        if isinstance(source_clock, dict):
            offset = float(source_clock.get("matchClockOffsetSeconds") or 0.0)
        return {
            "presentationTimeSeconds": presentation,
            "matchClockSeconds": presentation + offset,
            "explicitMapping": bool(source_clock),
            "frameAccurateOverlay": False,
            "sourceClockRecorded": bool(source_clock),
        }

    def incident_review_for_match(self, match_id: str) -> dict:
        from .workbench.incidents import level1_positional_aid

        match = self.get_match(match_id)
        frames = self.load_frames(match_id)
        if not frames:
            raise FileNotFoundError(match_id)
        geometry = self.incident_geometry_for_match(match_id)
        start = float(frames[0].timestamp)
        end = float(frames[1].timestamp) if len(frames) > 1 else start + 0.12
        attacker = geometry.get("mostAdvancedTeammateX")
        line = geometry.get("secondLastOpponentX")
        attacker_x = None if attacker is None else float(attacker)
        line_x = None if line is None else float(line)
        samples: list[tuple[float, float]] = []
        attacking_right_to_left = match.config.attackDirection == "right_to_left"
        if attacker_x is not None and line_x is not None:
            for frame in frames[:2]:
                xs = [float(player.x) for player in frame.myTeam]
                if xs:
                    samples.append((float(frame.timestamp), min(xs) if attacking_right_to_left else max(xs)))
        return level1_positional_aid(
            touch_interval=(start, end),
            attacker_x=attacker_x,
            offside_line_x=line_x,
            uncertainty_m=3.0,
            attacker_x_by_time=tuple(samples) if samples else None,
        )

    def dpia_for_match(self, match_id: str) -> dict:
        from .workbench.privacy import dpia_screen

        match = self.get_match(match_id)
        rights = match.config.rights
        cloud_requested = match.config.llmProvider == "cloud" or rights.processingScope != "local_only"
        return dpia_screen(
            youth_footage=False,
            identifiable_faces=True,
            cloud_requested=cloud_requested,
            cloud_permitted=rights.cloudPermission,
        ).model_dump(mode="json")

    def preview_landmark_for_match(self, match_id: str) -> dict:
        from .workbench.cache import REBUILD_FOR
        from .workbench.geometry import preview_landmark_fit

        match = self.get_match(match_id)
        try:
            stored = self.load_analysis_artifact(match_id, "calibration_profile")
        except FileNotFoundError:
            stored = None
        if stored and stored.get("committed"):
            evaluation = dict(stored.get("evaluation") or {})
            return {
                "preview": False,
                "committed": True,
                "certified": False,
                "accepted": bool(evaluation.get("accepted", True)),
                "measured": True,
                "visionRerun": False,
                "residualP95M": evaluation.get("p95M", stored.get("profile", {}).get("residualP95M") if isinstance(stored.get("profile"), dict) else None),
                "rebuild": list(REBUILD_FOR["calibration"]),
                "reasonCodes": [],
            }
        preview = preview_landmark_fit(residual_p95_m=float("inf"), max_p95_m=3.0)
        preview["residualP95M"] = None
        preview["measured"] = False
        preview["accepted"] = False
        preview["certified"] = False
        preview["rebuild"] = list(REBUILD_FOR["calibration"])
        preview["reasonCodes"] = ["LANDMARK_RESIDUAL_UNMEASURED"]
        preview["committed"] = bool(match.config.calibrationCommitted)
        return preview

    def commit_calibration_for_match(self, match_id: str, payload: dict) -> dict:
        from .workbench.geometry import CalibrationProfile, commit_calibration

        match = self.get_match(match_id)
        profile = CalibrationProfile.model_validate(payload)
        result = commit_calibration(profile)
        if result.get("committed"):
            self.save_analysis_artifact(match_id, "calibration_profile", result)
            self.update_match_config(
                match_id,
                match.config.model_copy(update={"calibrationCommitted": True}),
            )
        return result

    def recompute_for_match(self, match_id: str, change: str) -> dict:
        from .video_pipeline import IMAGE_SPACE_SAFE_CHANGES, reprocess_for_change
        from .workbench.cache import cache_identity

        self.get_match(match_id)
        if change not in IMAGE_SPACE_SAFE_CHANGES:
            return {
                "visionInvoked": False,
                "admitted": False,
                "reused": False,
                "rebuild": [],
                "reasonCodes": ["VISION_REQUIRES_SEALED_WORKER"],
            }
        sha = self.source_sha256(match_id)
        previous = cache_identity(
            source_sha256=sha,
            interval_start=0.0,
            interval_end=0.0,
            decoder_version="opencv",
            model_hash="weights-v1",
            temporal_policy="source_global_grid",
            output_schema="evidence_v1",
            namespace="production",
        )
        current = cache_identity(
            source_sha256=sha,
            interval_start=0.0,
            interval_end=0.0,
            decoder_version="opencv",
            model_hash="weights-v1",
            temporal_policy="source_global_grid",
            output_schema="evidence_v1",
            namespace="production",
            calibration_id=None if change == "report" else "preview",
        )

        def vision() -> dict:
            raise RuntimeError("image-space-safe recompute must not invoke vision")

        result = dict(
            reprocess_for_change(
                change=change,
                previous_identity=previous,
                current_identity=current,
                vision=vision,
            )
        )
        result["admitted"] = True
        return result

    def promotion_receipt_for_match(self, match_id: str) -> dict:
        from .workbench.receipts import promotion_receipt

        sha = self.source_sha256(match_id)
        try:
            frame_count = len(self.load_frames(match_id))
        except FileNotFoundError:
            frame_count = 0
        return promotion_receipt(
            source_sha256=sha,
            weights="unpromoted",
            configuration="evidence_v1",
            hardware="cpu",
            native_builds=[],
            selected_backend="opencv+ultralytics_track",
            frame_count=frame_count,
            call_count=0,
            cold_timing_ms=0.0,
            warm_timing_ms=0.0,
            peak_memory_bytes=0,
            transferred_bytes=0,
            output_quality="unproven",
            accepted_coverage=0.0,
            failure_cases=["labels_incomplete"],
            allocated_spend=0.0,
            fallback_event="cpu_local",
        )

    def assistance_fallback_for_match(self, match_id: str) -> dict:
        from .workbench.assistance import events_as_query_rows, providers_disabled_fallback

        self.get_match(match_id)
        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            events = []
        try:
            metrics = self.match_metrics_for_match(match_id)["metrics"]
        except FileNotFoundError:
            metrics = []
        return providers_disabled_fallback(
            metrics=metrics,
            events=events_as_query_rows(events, match_id=match_id),
        )

    def quality_timeline_for_match(self, match_id: str) -> dict:
        match = self.get_match(match_id)
        items: list[dict] = []
        try:
            players = self.player_observations_for_match(match_id)
        except FileNotFoundError:
            players = {"totalsWithheld": True, "reasonCodes": ["IDENTITY_DISCONTINUITY"]}
        if players.get("totalsWithheld") or "IDENTITY_DISCONTINUITY" in list(players.get("reasonCodes") or []):
            items.append({"id": "identity", "label": "identity switches", "impact": "high", "accepted": False})
        setup = self.assess_stored_match_setup(match_id)
        preview = self.preview_landmark_for_match(match_id)
        if not setup.get("certified") or preview.get("measured") is False:
            items.append({"id": "calibration", "label": "calibration drift", "impact": "high", "accepted": False})
        if match.config.myTeamCluster is None:
            items.append({"id": "team", "label": "incorrect team selection", "impact": "high", "accepted": False})
        try:
            ownership = self.classify_match_ownership(match_id)
        except FileNotFoundError:
            ownership = {"mode": "unknown"}
        if ownership.get("mode") == "unknown":
            items.append(
                {
                    "id": "possession",
                    "label": "ambiguous possession around a shot",
                    "impact": "high",
                    "accepted": False,
                }
            )
        return {"items": items, "reviewFirst": True, "accepted": False, "measured": False}

    def _stored_identity_continuous(self, match_id: str) -> bool:
        try:
            summary, _, _, _ = self.load_analytics(match_id)
        except FileNotFoundError:
            return False
        physical = next(
            (item for item in summary.metricAvailability if item.metric == "my_team_distance_m"),
            None,
        )
        return bool(
            physical is not None
            and physical.availability == "available"
            and "IDENTITY_DISCONTINUITY" not in (physical.reasonCodes or [])
        )

    def _stored_calibration_accepted(self, match_id: str) -> bool:
        try:
            payload = self.load_analysis_artifact(match_id, "calibration_evaluation")
        except FileNotFoundError:
            return False
        return bool(payload.get("accepted")) and payload.get("measured") is True

    def heatmap_for_match(self, match_id: str) -> dict:
        from .workbench.quantities import heatmap_availability

        self.get_match(match_id)
        return heatmap_availability(identity_continuous=self._stored_identity_continuous(match_id))

    def identity_for_match(self, match_id: str) -> dict:
        from .workbench.identity import (
            appearance_embedding_policy,
            candidate_rejoin,
            cross_season_identity,
            face_recognition,
            reconnect_across_cut,
        )
        from .workbench.media import detect_camera_cuts

        self.get_match(match_id)
        try:
            frames = self.load_frames(match_id)
        except FileNotFoundError:
            frames = []
        times = [float(frame.timestamp) for frame in frames]
        cuts = detect_camera_cuts(times) if len(times) > 1 else []
        payload = reconnect_across_cut(cut_detected=bool(cuts))
        payload["appearance"] = appearance_embedding_policy()
        payload["faceRecognition"] = face_recognition(requested=False)
        payload["crossSeasonIdentity"] = cross_season_identity(requested=False)
        payload["candidateRejoin"] = candidate_rejoin()
        payload["cutCount"] = len(cuts)
        payload["identityContinuous"] = self._stored_identity_continuous(match_id)
        return payload

    def repair_identity_for_match(self, match_id: str, payload: dict | None = None) -> dict:
        from .workbench.identity import (
            frames_have_identity_overlap,
            frames_with_track,
            next_available_track_id,
            rows_from_frames,
        )
        from .workbench.perception import IdentityRepair, preview_identity_change
        from .workbench.review import correction_api_payload

        self.get_match(match_id)
        body = dict(payload or {})
        kind = str(body.get("kind") or "track_split")
        track_id = str(body.get("trackId") or "")
        at_frame = int(body.get("atFrame") or 0)
        left_track_id = str(body.get("leftTrackId") or "")
        right_track_id = str(body.get("rightTrackId") or "")
        try:
            frames = self.load_frames(match_id)
        except FileNotFoundError:
            frames = []
        stored_ids = {str(row["trackId"]) for row in rows_from_frames(frames)}
        preview = preview_identity_change(
            kind=kind,
            track_id=track_id or None,
            at_frame=at_frame,
            interval_start=body.get("intervalStart"),
            interval_end=body.get("intervalEnd"),
        )
        known = False
        reason_codes: list[str] = []
        new_track_id: int | None = None
        if kind == "track_split":
            known = track_id in stored_ids
            if known:
                new_track_id = next_available_track_id(frames)
        elif kind == "track_join":
            known = left_track_id in stored_ids and right_track_id in stored_ids
            if known and frames_have_identity_overlap(frames, left_track_id, right_track_id):
                known = False
                reason_codes.append("IDENTITY_OVERLAP")
        if not known and "IDENTITY_OVERLAP" not in reason_codes:
            reason_codes.append("UNKNOWN_TRACK")
        repair = IdentityRepair()
        if kind == "track_join":
            repair.join(left_track_id or "t-1", right_track_id or "t-2", author=str(body.get("author") or "analyst"))
        else:
            repair.split(track_id or "t-1", at_frame, author=str(body.get("author") or "analyst"))
        correction = None
        committed = False
        if known and kind in {"track_split", "track_join"}:
            payload = {
                "trackId": track_id,
                "atFrame": at_frame,
                "leftTrackId": left_track_id,
                "rightTrackId": right_track_id,
            }
            if kind == "track_split" and new_track_id is not None:
                payload["newTrackId"] = new_track_id
            if kind == "track_join":
                payload["rightFrameIds"] = frames_with_track(frames, right_track_id)
            saved = self.submit_correction(
                match_id,
                kind=kind,
                payload=payload,
                author=str(body.get("author") or "analyst"),
            )
            correction = correction_api_payload(saved)
            committed = saved.saveState == "saved"
            if committed:
                self._apply_identity_edit(match_id, kind=kind, payload=payload)
                self._invalidate_stored_identity_continuity(match_id)
        return {
            **preview,
            "committed": committed,
            "identityContinuous": False,
            "silentlyReconnected": False,
            "visionRerun": False,
            "reasonCodes": reason_codes,
            "edits": repair.edits,
            "correction": correction,
            "storedTrack": known,
        }

    def promote_identity_for_match(self, match_id: str, payload: dict | None = None) -> dict:
        from .workbench.review import correction_api_payload

        self.get_match(match_id)
        body = dict(payload or {})
        reviewed = body.get("reviewed") is True
        reason_codes: list[str] = []
        correction = None
        committed = False
        if not reviewed:
            reason_codes.append("REVIEW_REQUIRED")
        else:
            saved = self.submit_correction(
                match_id,
                kind="identity_validate",
                payload={"reviewed": True},
                author=str(body.get("author") or "analyst"),
                crash_before_commit=bool(body.get("crashBeforeCommit")),
            )
            correction = correction_api_payload(saved)
            committed = saved.saveState == "saved"
        return {
            "preview": True,
            "committed": committed,
            "identityContinuous": self._stored_identity_continuous(match_id) if committed else False,
            "silentlyReconnected": False,
            "visionRerun": False,
            "reasonCodes": reason_codes,
            "correction": correction,
        }

    def _recompute_identity_continuity(self, match_id: str, *, identity_continuous: bool) -> None:
        from .analytics import summarize_match

        try:
            frames = self.load_frames(match_id)
            summary, assignments, timeline, shots = self.load_analytics(match_id)
        except FileNotFoundError:
            return
        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            events = []
        match = self.get_match(match_id)
        self.save_analytics(
            match_id,
            summarize_match(
                frames,
                assignments,
                shots,
                events,
                attack_direction=match.config.attackDirection,
                identity_continuous=identity_continuous,
            ),
            assignments,
            timeline,
            shots,
        )

    def _apply_identity_edit(self, match_id: str, *, kind: str, payload: dict) -> None:
        from .workbench.identity import apply_track_join, apply_track_split, apply_track_unjoin, remap_track_references

        try:
            frames = self.load_frames(match_id)
        except FileNotFoundError:
            return
        at_frame = int(payload.get("atFrame") or 0)
        frame_ids = None
        if kind == "track_split":
            source = str(payload.get("trackId") or "")
            dest = int(payload["newTrackId"])
            frames = apply_track_split(frames, track_id=source, at_frame=at_frame, new_track_id=dest)
        elif kind == "track_join":
            source = str(payload.get("rightTrackId") or "")
            dest = int(payload.get("leftTrackId"))
            frames = apply_track_join(frames, left_track_id=str(dest), right_track_id=source)
            at_frame = 0
        elif kind == "track_join_undo":
            source = str(payload.get("leftTrackId") or "")
            dest = int(payload.get("rightTrackId"))
            frame_ids = [int(frame_id) for frame_id in payload.get("rightFrameIds") or []]
            if not frame_ids:
                return
            frames = apply_track_unjoin(
                frames,
                left_track_id=source,
                right_track_id=str(dest),
                right_frame_ids=frame_ids,
            )
            at_frame = 0
        else:
            return
        self.save_frames(match_id, frames)
        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            events = []
        if events:
            self.save_events(
                match_id,
                remap_track_references(
                    events,
                    track_id=source,
                    new_track_id=dest,
                    at_frame=at_frame,
                    frame_ids=frame_ids,
                ),
            )
        try:
            summary, assignments, timeline, shots = self.load_analytics(match_id)
        except FileNotFoundError:
            return
        self.save_analytics(
            match_id,
            summary,
            remap_track_references(
                assignments,
                track_id=source,
                new_track_id=dest,
                at_frame=at_frame,
                frame_ids=frame_ids,
            ),
            timeline,
            remap_track_references(
                shots,
                track_id=source,
                new_track_id=dest,
                at_frame=at_frame,
                frame_ids=frame_ids,
            ),
        )

    def _invalidate_stored_identity_continuity(self, match_id: str) -> None:
        try:
            summary, assignments, timeline, shots = self.load_analytics(match_id)
        except FileNotFoundError:
            return
        physical_names = {
            "my_team_distance_m",
            "enemy_distance_m",
            "my_team_top_speed_kmh",
            "enemy_top_speed_kmh",
            "my_team_sprints",
            "enemy_sprints",
        }
        availability = []
        for item in summary.metricAvailability:
            if item.metric in physical_names:
                reasons = list(item.reasonCodes or [])
                if "IDENTITY_DISCONTINUITY" not in reasons:
                    reasons.append("IDENTITY_DISCONTINUITY")
                availability.append(
                    item.model_copy(
                        update={"availability": "withheld", "value": None, "reasonCodes": reasons}
                    )
                )
            else:
                availability.append(item)
        self.save_analytics(
            match_id,
            summary.model_copy(
                update={
                    "metricAvailability": availability,
                    "myTeamDistance": None,
                    "enemyDistance": None,
                    "myTeamTopSpeed": None,
                    "enemyTopSpeed": None,
                    "myTeamSprints": None,
                    "enemySprints": None,
                }
            ),
            assignments,
            timeline,
            shots,
        )

    def formation_for_match(self, match_id: str) -> dict:
        from .workbench.quantities import formation_availability

        match = self.get_match(match_id)
        try:
            _, _, timeline, _ = self.load_analytics(match_id)
        except FileNotFoundError:
            timeline = []
        role_context = match.config.myTeamCluster is not None
        return formation_availability(eligible_windows=len(timeline), role_context=role_context)

    def partition_events_for_match(self, match_id: str) -> dict:
        from .workbench.assistance import events_as_query_rows
        from .workbench.events import partition_events

        self.get_match(match_id)
        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            events = []
        return partition_events(events_as_query_rows(events, match_id=match_id))

    def provenance_for_match(self, match_id: str, claimed_evidence_ids: list[str] | None = None) -> dict:
        from .workbench.assistance import events_as_query_rows
        from .workbench.evidence import records_from_match
        from .workbench.reports import claim_provenance

        self.get_match(match_id)
        try:
            frames = self.load_frames(match_id)
        except FileNotFoundError:
            frames = []
        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            events = []
        known = {record.evidenceId for record in records_from_match(frames, events)}
        if claimed_evidence_ids is None:
            claims = [
                {"evidenceIds": list(row.get("evidenceIds") or [])}
                for row in events_as_query_rows(events, match_id=match_id)
            ]
        else:
            claims = [{"evidenceIds": list(claimed_evidence_ids)}]
        return claim_provenance(claims=claims, known_evidence_ids=known)

    def coverage_for_match(self, match_id: str) -> dict:
        from .workbench.assistance import events_as_query_rows
        from .workbench.reports import coverage_aware_selector

        self.get_match(match_id)
        try:
            frames = self.load_frames(match_id)
        except FileNotFoundError:
            frames = []
        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            events = []
        frame_rows = [{"frameId": frame.frameId, "timestamp": frame.timestamp} for frame in frames]
        return coverage_aware_selector(
            frames=frame_rows,
            events=events_as_query_rows(events, match_id=match_id),
            max_frames=3,
        )

    def shot_quality_for_match(self, match_id: str) -> dict:
        from .workbench.shot_model import experimental_shot_quality, extract_shot_features

        self.get_match(match_id)
        try:
            _, _, _, shots = self.load_analytics(match_id)
        except FileNotFoundError:
            shots = []
        items = []
        for shot in shots:
            features = extract_shot_features({"x": float(shot.x), "y": float(shot.y), "inBox": bool(shot.inBox)})
            items.append(experimental_shot_quality(features).model_dump(mode="json"))
        return {
            "publishedLabel": "experimental_shot_quality",
            "calibratedXg": False,
            "items": items,
        }

    def proxy_assets_for_match(self, match_id: str) -> dict:
        from .workbench.media import derive_proxy_assets, run_proxy_ffmpeg_job

        original = self.get_match_input_path(match_id)
        sha = self.source_sha256(match_id)
        try:
            frames = self.load_frames(match_id)
            pts = [int(float(frame.timestamp) * 90000) for frame in frames[:8]] or [0]
        except FileNotFoundError:
            pts = [0]
        destination = self._match_dir(match_id) / "proxy.mp4"
        try:
            receipt = dict(
                run_proxy_ffmpeg_job(
                    original,
                    destination,
                    original_sha256=sha,
                )
            )
            receipt["ranFfmpeg"] = True
            return receipt
        except (FileNotFoundError, ValueError, OSError, Exception):
            receipt = dict(
                derive_proxy_assets(original, original_sha256=sha, original_pts=pts, time_base=(1, 90000))
            )
            receipt["ranFfmpeg"] = False
            return receipt

    def edit_list_for_match(self, match_id: str) -> dict:
        from .workbench.media import store_edit_list

        sha = self.source_sha256(match_id)
        intervals: list[dict[str, float]] = []
        for payload in self._active_playlist_payloads(match_id):
            start = payload.get("timestampStart", payload.get("start"))
            end = payload.get("timestampEnd", payload.get("end"))
            if start is None or end is None:
                continue
            intervals.append({"start": float(start), "end": float(end)})
        if not intervals:
            intervals = [{"start": 0.0, "end": 0.0}]
        return store_edit_list(source_sha256=sha, intervals=intervals)

    def render_edit_for_match(self, match_id: str, *, start: float, end: float) -> dict:
        from .workbench.media import render_on_demand

        edits = self.edit_list_for_match(match_id)
        return render_on_demand(edits, start=start, end=end)

    def write_alongside_for_match(self, match_id: str) -> dict:
        from .workbench.artifacts import ArtifactStore, write_alongside

        self.get_match(match_id)
        store = ArtifactStore(self.storage_root / "artifacts")
        namespace = f"match:{match_id}"
        previous = store.put(b"report-v1", namespace=namespace)
        return write_alongside(store, previous_digest=previous, payload=b"report-v2", namespace=namespace)

    def tracklets_for_match(self, match_id: str) -> dict:
        from .workbench.identity import assign_tracklet, tracker_chunk
        from .workbench.media import detect_camera_cuts

        self.get_match(match_id)
        try:
            frames = self.load_frames(match_id)
            times = [float(frame.timestamp) for frame in frames]
            cuts = detect_camera_cuts(times) if len(times) > 1 else []
        except FileNotFoundError:
            cuts = []
        return {
            "assignment": assign_tracklet(roster_id=None, reviewed=False),
            "chunk": tracker_chunk(scene_discontinuity=bool(cuts), broadcast_replay=False),
            "silentlyReconnected": False,
        }

    def derived_distance_for_match(self, match_id: str) -> dict:
        from .workbench.geometry import derived_distance, from_legacy_four_points, path_distance_m
        from .workbench.media import detect_camera_cuts

        match = self.get_match(match_id)
        try:
            frames = self.load_frames(match_id)
            times = [float(frame.timestamp) for frame in frames]
            cuts = detect_camera_cuts(times) if len(times) > 1 else []
        except FileNotFoundError:
            frames = []
            cuts = []
        identity_gap = not self._stored_identity_continuous(match_id)
        calibration_missing = not self._stored_calibration_accepted(match_id)
        evaluation = self._load_calibration_evaluation(match_id)
        residual = evaluation.get("p95M")
        uncertainty_m = float(residual) if residual is not None else 0.0
        points = [{"x": float(point.x), "y": float(point.y)} for point in match.config.manualHomographyPoints]
        if len(points) != 4:
            points = [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}, {"x": 1.0, "y": 1.0}, {"x": 0.0, "y": 1.0}]
        profile = from_legacy_four_points(points, calibration_id=match_id)
        delta_m = 0.0
        if frames and not identity_gap and not calibration_missing and not cuts:
            delta_m = path_distance_m(frames, profile)
        return derived_distance(
            delta_m=delta_m,
            uncertainty_m=uncertainty_m,
            cut_bridged=bool(cuts),
            identity_gap=identity_gap,
            calibration_missing=calibration_missing,
        )

    def shot_features_for_match(self, match_id: str) -> dict:
        from .workbench.shot_model import missing_shot_features

        self.get_match(match_id)
        try:
            _, _, _, shots = self.load_analytics(match_id)
        except FileNotFoundError:
            shots = []
        if not shots:
            record = missing_shot_features({})
            return {"recorded": True, "missing": list(record["missing"]), "imputedAsCalibrated": False}
        missing: list[str] = []
        for shot in shots:
            record = missing_shot_features({"x": shot.x, "y": shot.y, "inBox": shot.inBox})
            missing.extend(record["missing"])
        return {"recorded": True, "missing": sorted(set(missing)), "imputedAsCalibrated": False}

    def corrupted_import_for_match(self, match_id: str, actual_sha256: str) -> dict:
        from .workbench.recovery import corrupted_import

        expected = self.source_sha256(match_id)
        return corrupted_import(expected_sha256=expected, actual_sha256=actual_sha256)

    def restore_exercise_run(self) -> dict:
        from .workbench.recovery import restore_exercise

        return restore_exercise(self.storage_root / "restore-source", self.storage_root / "restore-dest")

    def history_for_match(self, match_id: str) -> dict:
        from .workbench.review import change_history

        self.get_match(match_id)
        return change_history(self.list_corrections(match_id))

    def cache_identity_for_match(self, match_id: str) -> dict:
        from .workbench.cache import cache_compatible, cache_identity

        sha = self.source_sha256(match_id)
        production = cache_identity(
            source_sha256=sha,
            interval_start=0.0,
            interval_end=0.0,
            decoder_version="opencv",
            model_hash="weights-v1",
            temporal_policy="source_global_grid",
            output_schema="evidence_v1",
            namespace="production",
        )
        development = cache_identity(
            source_sha256=sha,
            interval_start=0.0,
            interval_end=0.0,
            decoder_version="opencv",
            model_hash="weights-v1",
            temporal_policy="source_global_grid",
            output_schema="evidence_v1",
            namespace="development",
        )
        return {
            "namespace": "production",
            "identity": production,
            "compatibleWithDevelopment": cache_compatible(production, development),
        }

    def migrate_legacy_for_match(self, match_id: str) -> dict:
        from .workbench.evidence import migrate_legacy_record, rollback_reader

        summary, *_ = self.load_analytics(match_id)
        migrated = migrate_legacy_record(
            {
                "possession": summary.possession,
                "myTeamDistance": None,
                "enemyDistance": None,
                "controlledFrames": 0,
            }
        )
        return {"migrated": migrated, "rollback": rollback_reader(migrated), "rewrotePastOutcomes": False}

    def attack_direction_for_match(self, match_id: str, *, team: str, period: int) -> dict:
        from .workbench.quantities import attack_direction_for

        match = self.get_match(match_id)
        mapping = {("my_team", 1): match.config.attackDirection}
        return {
            "direction": attack_direction_for(team=team, period=period, mapping=mapping),
            "fromStoredConfig": True,
            "team": team,
            "period": period,
        }

    def interrupted_upload_run(self) -> dict:
        from .workbench.recovery import interrupted_upload

        return interrupted_upload(self.storage_root / "uploads" / "interrupted.bin")

    def calibration_for_match(self, match_id: str, payload: dict | None = None) -> dict:
        from .workbench.geometry import Landmark, evaluate_landmarks, from_legacy_four_points, withhold_if_invalid
        from .workbench.review import correction_api_payload

        match = self.get_match(match_id)
        points = [{"x": float(point.x), "y": float(point.y)} for point in match.config.manualHomographyPoints]
        if len(points) != 4:
            points = [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}, {"x": 1.0, "y": 1.0}, {"x": 0.0, "y": 1.0}]
        profile = from_legacy_four_points(points, calibration_id=match_id)
        body = dict(payload or {})
        holdout: list = []
        for item in body.get("landmarks") or []:
            if not isinstance(item, dict) or item.get("independentHoldout") is not True:
                continue
            holdout.append(
                Landmark(
                    name=str(item.get("name") or f"holdout_{len(holdout)}"),
                    imageX=float(item.get("imageX") or 0.0),
                    imageY=float(item.get("imageY") or 0.0),
                    pitchX=float(item.get("pitchX") or 0.0),
                    pitchY=float(item.get("pitchY") or 0.0),
                    independentHoldout=True,
                )
            )
        stored = self._load_calibration_evaluation(match_id)
        committed = False
        correction = None
        measured = False
        residual = None
        if holdout:
            profile = profile.model_copy(update={"landmarks": list(profile.landmarks) + holdout})
            measured_evaluation = evaluate_landmarks(profile, max_p95_m=3.0)
            saved = self.submit_correction(
                match_id,
                kind="calibration",
                payload={
                    "evaluation": {**measured_evaluation, "measured": True},
                    "previous": stored,
                },
                author=str(body.get("author") or "analyst"),
                crash_before_commit=bool(body.get("crashBeforeCommit")),
            )
            correction = correction_api_payload(saved)
            committed = saved.saveState == "saved"
            if committed:
                evaluation = measured_evaluation
                measured = True
                residual = measured_evaluation.get("p95M")
                stored = {**measured_evaluation, "measured": True}
            else:
                evaluation = {
                    "accepted": False,
                    "reasonCodes": ["CALIBRATION_UNAVAILABLE"],
                    "holdoutCount": len(holdout),
                }
        elif stored:
            evaluation = {
                "accepted": bool(stored.get("accepted")),
                "p95M": stored.get("p95M"),
                "holdoutCount": stored.get("holdoutCount") or 0,
                "farSideMaxM": stored.get("farSideMaxM"),
                "reasonCodes": list(stored.get("reasonCodes") or []),
            }
            measured = stored.get("measured") is True
            residual = stored.get("p95M") if measured else None
        else:
            evaluation = evaluate_landmarks(profile, max_p95_m=3.0)
        withheld = withhold_if_invalid(profile, "team_width_m")
        if stored.get("accepted") and stored.get("measured") is True:
            withheld = {"metric": "team_width_m", "availability": "available", "reasonCodes": [], "value": "computed"}
        elif stored or committed is False:
            withheld = {"metric": "team_width_m", "availability": "withheld", "reasonCodes": list(evaluation.get("reasonCodes") or ["CALIBRATION_UNAVAILABLE"]), "value": None}
        return {
            **profile.model_dump(mode="json"),
            "evaluation": evaluation,
            "withheld": withheld,
            "fromStoredPoints": True,
            "measured": measured,
            "residualP95M": residual,
            "committed": committed,
            "visionRerun": False,
            "correction": correction,
        }

    def _load_calibration_evaluation(self, match_id: str) -> dict:
        try:
            payload = self.load_analysis_artifact(match_id, "calibration_evaluation")
        except FileNotFoundError:
            return {}
        return dict(payload) if isinstance(payload, dict) else {}

    def _save_calibration_evaluation(self, match_id: str, evaluation: dict) -> None:
        if not evaluation:
            path = self._match_dir(match_id) / "calibration_evaluation.json"
            if path.exists():
                path.unlink()
            return
        self.save_analysis_artifact(match_id, "calibration_evaluation", evaluation)

    def _restore_calibration_evaluation(self, match_id: str, previous: dict) -> None:
        self._save_calibration_evaluation(match_id, previous)

    def load_raw_rows(self, match_id: str) -> list[dict]:
        payload = self._read_json(self._match_dir(match_id) / "raw_rows.json")
        return [dict(item) for item in payload]

    def load_analytics(self, match_id: str) -> tuple[MatchSummary, list[BallOwnership], list[FormationSegment], list[ShotAnalytics]]:
        payload = self._read_json(self._match_dir(match_id) / "analytics.json")
        summary = self._video_ball_signal_summary(match_id, MatchSummary.model_validate(payload["summary"]))
        assignments = [BallOwnership.model_validate(item) for item in payload["ballAssignments"]]
        if not any(assignment.team in {"my_team", "enemy"} for assignment in assignments):
            summary = summary.model_copy(update={"possession": None})
        formation_timeline = [FormationSegment.model_validate(item) for item in payload.get("formationTimeline", [])]
        shots = [ShotAnalytics.model_validate(item) for item in payload.get("shots", [])]
        return summary, assignments, formation_timeline, shots

    def load_events(self, match_id: str) -> list[DetectedEvent]:
        payload = self._read_json(self._match_dir(match_id) / "events.json")
        return [DetectedEvent.model_validate(item) for item in payload]

    def load_analysis_artifact(self, match_id: str, analysis_type: str) -> dict:
        payload = self._read_json(self._match_dir(match_id) / f"{analysis_type}.json")
        return dict(payload)

    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        with Storage._atomic_text_destination(path) as handle:
            json.dump(payload, handle, indent=2)

    @staticmethod
    def _write_json_array(path: Path, values: Iterable[object]) -> None:
        encoder = json.JSONEncoder(separators=(",", ":"))
        with Storage._atomic_text_destination(path) as handle:
            handle.write("[")
            for index, value in enumerate(values):
                if index:
                    handle.write(",")
                for chunk in encoder.iterencode(value):
                    handle.write(chunk)
            handle.write("]")

    @staticmethod
    @contextmanager
    def _atomic_text_destination(path: Path) -> Iterator[TextIO]:
        """Publish text durably, restoring the prior path on commit failure."""
        temporary_fd, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        backup: Path | None = None
        directory_fd = -1
        published = False
        rollback_uncertain = False
        try:
            handle = os.fdopen(temporary_fd, "w", encoding="utf-8")
            temporary_fd = -1
            with handle:
                yield handle
                handle.flush()
                os.fsync(handle.fileno())

            directory_fd = os.open(
                path.parent,
                os.O_RDONLY
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                prior = os.stat(path, follow_symlinks=False)
            except FileNotFoundError:
                prior = None
            if prior is not None:
                if not stat.S_ISREG(prior.st_mode):
                    raise OSError("atomic JSON destination is not a regular file")
                backup = path.with_name(f".{path.name}.{uuid.uuid4().hex}.bak")
                os.link(path, backup, follow_symlinks=False)
                retained = os.stat(backup, follow_symlinks=False)
                if (retained.st_dev, retained.st_ino) != (prior.st_dev, prior.st_ino):
                    raise OSError("atomic JSON destination changed before backup")
                os.fsync(directory_fd)

            os.replace(temporary, path)
            published = True
            os.fsync(directory_fd)
            if backup is not None:
                try:
                    backup.unlink()
                    backup = None
                except OSError:
                    pass  # The durable new path is authoritative; cleanup may retry below.
        except BaseException as error:
            if published:
                try:
                    if backup is None:
                        path.unlink()
                    else:
                        os.replace(backup, path)
                        backup = None
                    os.fsync(directory_fd)
                except BaseException:
                    rollback_uncertain = True
                    raise StorageWriteOutcomeUncertain(
                        "atomic JSON write outcome is uncertain; inspect before retrying"
                    ) from error
            raise
        finally:
            if temporary_fd >= 0:
                os.close(temporary_fd)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            if backup is not None and not rollback_uncertain:
                try:
                    backup.unlink(missing_ok=True)
                except OSError:
                    pass
            if directory_fd >= 0:
                try:
                    os.close(directory_fd)
                except OSError:
                    pass

    @staticmethod
    def _read_json(path: Path) -> object:
        return json.loads(path.read_text(encoding="utf-8"))

    # ===== Review Bundles / Playlists =====

    def _bundle_dir(self) -> Path:
        path = self.storage_root / "bundles"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def list_review_bundles(self, tags: list[str] | None = None) -> list[ReviewBundle]:
        """List all bundles, optionally filtered by tags."""
        with self._review_bundle_lock:
            bundles_dir = self._bundle_dir()
            bundles = []
            for bundle_file in bundles_dir.glob("*.json"):
                try:
                    data = self._read_json(bundle_file)
                    bundle = ReviewBundle.model_validate(data)
                except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as error:
                    raise ReviewBundleCorruptError(
                        f"review bundle {bundle_file.stem!r} is corrupt"
                    ) from error
                if tags and not any(tag in bundle.tags for tag in tags):
                    continue
                bundles.append(bundle)
        
        # Sort by updatedAt descending
        bundles.sort(key=lambda b: b.updatedAt, reverse=True)
        return bundles

    def get_review_bundle(self, bundle_id: str) -> ReviewBundle:
        """Load a single bundle by ID."""
        bundle_path = self._bundle_dir() / f"{bundle_id}.json"
        if not bundle_path.exists():
            raise KeyError(bundle_id)
        data = self._read_json(bundle_path)
        return ReviewBundle.model_validate(data)

    def create_review_bundle(self, name: str, description: str = "", items: list = None, tags: list[str] | None = None) -> ReviewBundle:
        """Create a new review bundle."""
        bundle_id = uuid.uuid4().hex
        now = _utcnow().isoformat()
        bundle = ReviewBundle(
            id=bundle_id,
            name=name,
            description=description,
            items=items or [],
            tags=tags or [],
            createdAt=now,
            updatedAt=now,
        )
        bundle_path = self._bundle_dir() / f"{bundle_id}.json"
        self._write_json(bundle_path, bundle.model_dump(mode="json"))
        return bundle

    def update_review_bundle(self, bundle_id: str, name: str | None = None, description: str | None = None, items: list | None = None, tags: list[str] | None = None) -> ReviewBundle:
        """Update an existing bundle."""
        with self._review_bundle_lock:
            bundle = self.get_review_bundle(bundle_id)
            now = _utcnow().isoformat()
            if name is not None:
                bundle.name = name
            if description is not None:
                bundle.description = description
            if items is not None:
                bundle.items = items
            if tags is not None:
                bundle.tags = tags
            bundle.updatedAt = now
            bundle_path = self._bundle_dir() / f"{bundle_id}.json"
            self._write_json(bundle_path, bundle.model_dump(mode="json"))
            return bundle

    def delete_review_bundle(self, bundle_id: str) -> None:
        """Delete a bundle."""
        with self._review_bundle_lock:
            bundle_path = self._bundle_dir() / f"{bundle_id}.json"
            tombstone = bundle_path.with_name(
                f".{bundle_path.name}.{uuid.uuid4().hex}.deleted"
            )
            directory_fd = os.open(
                bundle_path.parent,
                os.O_RDONLY
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_DIRECTORY", 0),
            )
            renamed = committed = False
            try:
                try:
                    target = os.stat(bundle_path, follow_symlinks=False)
                except FileNotFoundError:
                    raise KeyError(bundle_id) from None
                if not stat.S_ISREG(target.st_mode):
                    raise OSError("review bundle is not a regular file")
                os.replace(bundle_path, tombstone)
                renamed = True
                os.fsync(directory_fd)
                committed = True
                try:
                    tombstone.unlink()
                    renamed = False
                    os.fsync(directory_fd)
                except OSError:
                    pass  # The visible deletion is already durable.
            except BaseException as error:
                if renamed and not committed:
                    try:
                        os.replace(tombstone, bundle_path)
                        renamed = False
                        os.fsync(directory_fd)
                    except BaseException:
                        raise StorageDeleteOutcomeUncertain(
                            "review bundle deletion outcome is uncertain; inspect before retrying"
                        ) from error
                raise
            finally:
                if committed and renamed:
                    try:
                        tombstone.unlink(missing_ok=True)
                    except OSError:
                        pass
                try:
                    os.close(directory_fd)
                except OSError:
                    pass

    # ===== Annotations =====

    def _annotations_path(self, match_id: str) -> Path:
        self.get_match(match_id)
        path = self.storage_root / "matches" / match_id / "annotations.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def list_annotations(self, match_id: str) -> list[TacticalAnnotationRecord]:
        """Load all annotations for a match."""
        path = self._annotations_path(match_id)
        if not path.exists():
            return []
        data = self._read_json(path)
        if not isinstance(data, list):
            raise TypeError("annotations must be a JSON array")
        return [TacticalAnnotationRecord.model_validate(a) for a in data]

    def create_annotation(self, match_id: str, payload: CreateAnnotationRequest) -> TacticalAnnotationRecord:
        """Append a new annotation to a match's annotation list."""
        now = _utcnow().isoformat()
        record = TacticalAnnotationRecord(
            id=uuid.uuid4().hex,
            matchId=match_id,
            createdAt=now,
            updatedAt=now,
            **{k: v for k, v in payload.model_dump().items() if v is not None},
        )
        with self._annotation_issue_lock:
            annotations = self.list_annotations(match_id)
            annotations.append(record)
            self._write_json(self._annotations_path(match_id), [a.model_dump(mode="json") for a in annotations])
        return record

    def delete_annotation(self, match_id: str, annotation_id: str) -> None:
        """Remove an annotation by ID."""
        with self._annotation_issue_lock:
            annotations = [a for a in self.list_annotations(match_id) if a.id != annotation_id]
            self._write_json(self._annotations_path(match_id), [a.model_dump(mode="json") for a in annotations])

    # ===== Match Issues =====

    def _issues_path(self, match_id: str) -> Path:
        self.get_match(match_id)
        path = self.storage_root / "matches" / match_id / "issues.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def list_issues(self, match_id: str) -> list[MatchIssueRecord]:
        """Load all issues for a match."""
        path = self._issues_path(match_id)
        if not path.exists():
            return []
        data = self._read_json(path)
        if not isinstance(data, list):
            raise TypeError("issues must be a JSON array")
        return [MatchIssueRecord.model_validate(i) for i in data]

    def create_issue(self, match_id: str, payload: CreateIssueRequest) -> MatchIssueRecord:
        """Append a new issue to a match's issue list."""
        now = _utcnow().isoformat()
        record = MatchIssueRecord(
            id=uuid.uuid4().hex,
            matchId=match_id,
            createdAt=now,
            updatedAt=now,
            **{k: v for k, v in payload.model_dump().items() if v is not None},
        )
        with self._annotation_issue_lock:
            issues = self.list_issues(match_id)
            issues.append(record)
            self._write_json(self._issues_path(match_id), [i.model_dump(mode="json") for i in issues])
        return record

    def delete_issue(self, match_id: str, issue_id: str) -> None:
        """Remove an issue by ID."""
        with self._annotation_issue_lock:
            issues = [i for i in self.list_issues(match_id) if i.id != issue_id]
            self._write_json(self._issues_path(match_id), [i.model_dump(mode="json") for i in issues])

    # ===== Semantic Search Support =====

    def _indexed_match_summary(self, match_id: str, encoded: str | None) -> MatchSummary:
        if encoded:
            try:
                return MatchSummary.model_validate_json(encoded)
            except ValidationError:
                pass
        summary, _, _, _ = self.load_analytics(match_id)
        with self._connect() as connection:
            connection.execute(
                "UPDATE matches SET analytics_summary_json = ? WHERE id = ?",
                (summary.model_dump_json(), match_id),
            )
        return summary

    def list_matches_with_analytics(self) -> list[dict]:
        """List all matches that have analytics available.
        
        Returns list of dicts with matchId, matchName, summary for each match.
        """
        with self._connect() as connection:
            matches = connection.execute(
                """
                SELECT id, name, created_at, analytics_summary_json
                FROM matches
                WHERE status IN ('completed', 'ready')
                ORDER BY created_at DESC
                """
            ).fetchall()
        results = []

        for match in matches:
            try:
                summary = self._indexed_match_summary(match["id"], match["analytics_summary_json"])
                results.append({
                    "matchId": match["id"],
                    "matchName": match["name"],
                    "summary": summary.model_dump(mode="json"),
                    "createdAt": match["created_at"],
                })
            except FileNotFoundError:
                continue

        return results

    def get_match_summary_for_search(self, match_id: str) -> dict | None:
        """Get match summary data for search indexing.
        
        Returns dict with summary data or None if not available.
        """
        with self._connect() as connection:
            match = connection.execute(
                "SELECT id, name, analytics_summary_json FROM matches WHERE id = ?",
                (match_id,),
            ).fetchone()
        if match is None:
            return None
        try:
            summary = self._indexed_match_summary(match_id, match["analytics_summary_json"])
            return {
                "matchId": match_id,
                "matchName": match["name"],
                "summary": summary.model_dump(mode="json"),
            }
        except FileNotFoundError:
            return None
