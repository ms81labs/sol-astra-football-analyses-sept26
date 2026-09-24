"""Job and admission persistence implementation for the Storage facade."""

from __future__ import annotations

import hashlib
import logging
import os
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .schemas import JobRecord, MatchConfig, MatchRecord


LOGGER = logging.getLogger(__name__)
_COPY_CHUNK_BYTES = 64 * 1024


class JobCancellationRequested(RuntimeError):
    pass


class AdmissionOutcomeUncertainError(RuntimeError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _JobStorageMixin:
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
        authorised_location: str = "local",
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
        self._admit_durable_job(
            match_id,
            job_id,
            budget=budget,
            namespace=namespace,
            authorised_location=authorised_location,
        )
        return self.get_job(job_id), True


    def _admit_durable_job(
        self,
        match_id: str,
        job_id: str,
        *,
        budget: float = 0.0,
        namespace: str = "production",
        authorised_location: str = "local",
    ) -> None:
        from .workbench.jobs import JobRequest

        if self.job_ledger.has_request(job_id):
            return
        try:
            sha = self.source_sha256(match_id)
        except Exception as exc:
            LOGGER.warning(
                "source hash unavailable; admitting fallback identity match=%s job=%s error=%s",
                match_id,
                job_id,
                type(exc).__name__,
            )
            sha = "0" * 64
        self.job_ledger.admit(
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
                authorisedLocation=authorised_location,  # type: ignore[arg-type]
                namespace=namespace,  # type: ignore[arg-type]
            ),
            mode="submit",
            owner_id=f"job:{job_id}",
            lease_seconds=60.0,
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
                LOGGER.warning("job admission rollback failed")
            try:
                connection.close()
            except Exception:
                LOGGER.warning("job admission connection close failed")
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
                LOGGER.warning("committed job admission connection close failed")
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
        actual_cost: float | None = 0.0,
        ledger_outcome_unknown: bool = False,
    ) -> JobRecord:
        now = _utcnow().isoformat()
        ledger = getattr(self, "job_ledger", None)
        if (
            ledger is not None
            and ledger.has_request(job_id)
            and ledger.cancel_requested(job_id)
            and status != "cancelled"
        ):
            raise JobCancellationRequested(job_id)
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
            if status in {"completed", "failed", "cancelled"}:
                if started_at is None:
                    started_at = now
                completed_at = now

        mapped = {
            "completed": "complete",
            "complete": "complete",
            "failed": "failed",
            "cancelled": "cancelled",
        }.get(status)
        if ledger is not None and ledger.has_request(job_id):
            attempt = ledger.latest_attempt(job_id)
            if status == "processing":
                if attempt.status == "submitted":
                    ledger.transition(
                        attempt.attemptId,
                        expected_revision=attempt.revision,
                        owner_id=f"job:{job_id}",
                        status="running",
                    )
                else:
                    ledger.heartbeat(
                        attempt.attemptId,
                        owner_id=f"job:{job_id}",
                        lease_seconds=60.0,
                    )
            elif ledger_outcome_unknown or (self._remote_cost_unsettled and mapped is not None):
                ledger.transition(
                    attempt.attemptId,
                    expected_revision=attempt.revision,
                    owner_id=f"job:{job_id}",
                    status="outcome_unknown",
                    cleanupResult="unknown",
                    error="provider_cost_unsettled",
                )
            elif mapped:
                ledger.transition(
                    attempt.attemptId,
                    expected_revision=attempt.revision,
                    owner_id=f"job:{job_id}",
                    status=mapped,
                    actualCost=actual_cost,
                )
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, progress = ?, message = ?, error = ?, runpod_run_id = ?, started_at = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, progress, message, error, persisted_remote_run_id, started_at, completed_at, now, job_id),
            )
        return self.get_job(job_id)


    def reset_job_for_retry(self, job_id: str) -> JobRecord:
        now = _utcnow().isoformat()
        with self._connect() as connection:
            updated = connection.execute(
                """
                UPDATE jobs
                SET status='queued', progress=0, message='Queued', error=NULL,
                    started_at=NULL, completed_at=NULL, updated_at=?
                WHERE id=?
                """,
                (now, job_id),
            )
        if updated.rowcount != 1:
            raise KeyError(job_id)
        return self.get_job(job_id)


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

