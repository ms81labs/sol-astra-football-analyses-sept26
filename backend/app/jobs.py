from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .settings import ProcessingSettings
from .workbench.jobs import DurableJobLedger, JobAttempt, JobRequest
from .workbench.contracts import JobPhase


class JobDispatchError(RuntimeError):
    """Raised when the selected processing backend cannot be dispatched safely."""

    def __init__(self, message: str, *, child_may_have_started: bool = False):
        super().__init__(message)
        self.child_may_have_started = child_may_have_started


def run_job(storage_root: Path, job_id: str) -> None:
    from .worker import run_job as execute_job

    execute_job(storage_root, job_id)


class JobRunner:
    def __init__(
        self,
        storage_root: Path,
        run_jobs_inline: bool = False,
        settings: ProcessingSettings | None = None,
        ledger: DurableJobLedger | None = None,
    ):
        self.storage_root = Path(storage_root)
        self.run_jobs_inline = run_jobs_inline
        self.settings = settings or ProcessingSettings.from_env()
        self.ledger = ledger or DurableJobLedger(db_path=self.storage_root / "guerilla.sqlite3")

    def admit(
        self,
        job_id: str,
        *,
        match_id: str,
        source_sha256: str,
        budget: float = 0.0,
        namespace: str = "production",
    ) -> JobAttempt:
        if job_id in self.ledger.requests:
            return self.ledger.attempts[job_id][-1]
        location = "daytona" if self.settings.processing_backend == "daytona" else "local"
        return self.ledger.submit(
            JobRequest(
                requestId=job_id,
                matchId=match_id,
                sourceSha256=source_sha256,
                intervalStart=0.0,
                intervalEnd=0.0,
                temporalPolicy="source_global_grid",
                decoderVersion="opencv",
                modelHash="unspecified",
                outputSchema="evidence_v1",
                budget=budget,
                authorisedLocation=location,
                namespace=namespace,  # type: ignore[arg-type]
            )
        )

    def receipt(self, job_id: str) -> JobPhase:
        return self.ledger.receipt(job_id)

    def retry(self, job_id: str) -> JobAttempt:
        return self.ledger.retry(job_id)

    def _ensure_admitted(self, job_id: str) -> None:
        if job_id not in self.ledger.requests:
            self.admit(job_id, match_id="unknown", source_sha256="0" * 64, namespace="development")

    def start(self, job_id: str) -> None:
        self._ensure_admitted(job_id)
        try:
            self._dispatch(job_id)
        except JobDispatchError as exc:
            if exc.child_may_have_started:
                self.ledger.lost_connection(job_id)
            else:
                self.ledger.transition(job_id, "failed", error="dispatch_failed")
            raise

    def _dispatch(self, job_id: str) -> None:
        backend = self.settings.processing_backend
        if backend == "daytona":
            if self.run_jobs_inline:
                from .remote_worker import run_remote_job

                try:
                    run_remote_job(self.storage_root, job_id, settings=self.settings)
                except Exception:
                    raise JobDispatchError(
                        "inline job dispatch outcome is uncertain",
                        child_may_have_started=True,
                    ) from None
            else:
                self._spawn_daytona_worker(job_id)
            return
        if backend == "local":
            if self.run_jobs_inline:
                try:
                    run_job(self.storage_root, job_id)
                except Exception:
                    raise JobDispatchError(
                        "inline job dispatch outcome is uncertain",
                        child_may_have_started=True,
                    ) from None
                return

            self._spawn_local_worker(job_id)
            return
        raise JobDispatchError("selected processing backend is not available")

    def _spawn_daytona_worker(self, job_id: str) -> None:
        self._spawn_worker(
            job_id,
            module="backend.app.remote_worker",
            backend="daytona",
            daytona_api_key=self.settings.daytona_api_key,
        )

    def _spawn_local_worker(self, job_id: str) -> None:
        self._spawn_worker(
            job_id,
            module="backend.app.worker",
            backend="local",
        )

    def _spawn_worker(
        self,
        job_id: str,
        *,
        module: str,
        backend: str,
        daytona_api_key: str | None = None,
    ) -> None:
        log_path = self.storage_root / "logs" / f"job_{job_id}.log"
        if backend == "daytona":
            if not isinstance(daytona_api_key, str) or not daytona_api_key.strip():
                raise JobDispatchError("Daytona job configuration is unavailable")
        child_started = False
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            env = {
                key: value
                for key, value in os.environ.items()
                if not key.startswith(("RUNPOD_", "DAYTONA_"))
            }
            repo_root = str(Path(__file__).resolve().parents[2])
            current_pythonpath = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = repo_root if not current_pythonpath else f"{repo_root}:{current_pythonpath}"
            env["QT_QPA_PLATFORM"] = "offscreen"
            env["PROCESSING_BACKEND"] = backend
            if backend == "daytona":
                env["DAYTONA_API_KEY"] = daytona_api_key
            with open(log_path, "w") as log_file:
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        module,
                        "--storage-root",
                        str(self.storage_root),
                        "--job-id",
                        job_id,
                    ],
                    cwd=repo_root,
                    env=env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                )
                child_started = True
        except Exception:
            raise JobDispatchError(
                "job dispatch failed",
                child_may_have_started=child_started,
            ) from None
