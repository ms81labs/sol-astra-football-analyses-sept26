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
    "events.json",
    "tactical_report.json",
    "drills.json",
    "frames.json",
    "input_video_identity.json",
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

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

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

    def ensure_job(self, match_id: str, job_id: str, *, created_status: str = "queued") -> tuple[JobRecord, bool]:
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
        return self.get_job(job_id), True

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
        return self.get_job(job_id)

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

        with self._annotation_issue_lock:
            log = self._load_correction_log(match_id)
            saved = log.submit(
                new_correction(match_id, kind, payload or {}, author=author),  # type: ignore[arg-type]
                crash_before_commit=crash_before_commit,
                expected_version=expected_version,
            )
            self._save_correction_log(match_id, log)
            return saved

    def recover_correction(self, match_id: str, correction_id: str):
        with self._annotation_issue_lock:
            log = self._load_correction_log(match_id)
            saved = log.recover(correction_id)
            if saved.matchId != match_id:
                raise KeyError(correction_id)
            self._save_correction_log(match_id, log)
            return saved

    def undo_correction(self, match_id: str, correction_id: str, *, author: str = "analyst"):
        with self._annotation_issue_lock:
            log = self._load_correction_log(match_id)
            saved = log.undo(correction_id, author=author)
            self._save_correction_log(match_id, log)
            return saved

    def list_corrections(self, match_id: str, *, state: str | None = None) -> list[dict]:
        log = self._load_correction_log(match_id)
        items = log.pending(match_id) if state == "pending" else log.history(match_id)
        return [item.model_dump(mode="json") for item in items]

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
                identity_continuous=False,
                calibration_accepted=False,
                controlled_frames=controlled,
            )
        ]
        event_rows = events_as_query_rows(events, match_id=match_id)
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

        return player_observations(rows_from_frames(self.load_frames(match_id)), identity_continuous=False)

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
                identity_continuous=False,
                calibration_accepted=False,
                controlled_frames=controlled,
            )
        ]
        corrections = self.list_corrections(match_id)
        playlist = [item.get("payload") or item for item in corrections if item.get("kind") == "playlist_item"]
        return assemble_match_package(
            playlist=playlist,
            events=events_as_query_rows(events, match_id=match_id),
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
                identity_continuous=False,
                calibration_accepted=False,
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
        clips = [
            item.get("payload") or item
            for item in self.list_corrections(match_id)
            if item.get("kind") == "playlist_item"
        ]
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
        attacker_x = float(attacker) if attacker is not None else 0.0
        line_x = float(line) if line is not None else 0.0
        samples: list[tuple[float, float]] = []
        attacking_right_to_left = match.config.attackDirection == "right_to_left"
        for frame in frames[:2]:
            xs = [float(player.x) for player in frame.myTeam]
            if xs:
                samples.append((float(frame.timestamp), min(xs) if attacking_right_to_left else max(xs)))
            else:
                samples.append((float(frame.timestamp), attacker_x))
        if not samples:
            samples = [(start, attacker_x), (end, attacker_x)]
        return level1_positional_aid(
            touch_interval=(start, end),
            attacker_x=attacker_x,
            offside_line_x=line_x,
            uncertainty_m=3.0,
            attacker_x_by_time=tuple(samples),
        )

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
