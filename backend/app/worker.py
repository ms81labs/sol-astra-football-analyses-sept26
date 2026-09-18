from __future__ import annotations

import argparse
import traceback
from pathlib import Path

from .processor import process_match
from .storage import JobCancellationRequested, Storage
from .workbench.jobs import maintain_job_lease


def _confirm_cancelled(storage: Storage, job_id: str) -> None:
    storage.update_job(
        job_id,
        status="cancelled",
        progress=1.0,
        message="Cancelled",
    )
    storage.job_ledger.confirm_termination(
        job_id,
        owner_id=f"job:{job_id}",
    )
    storage.job_ledger.confirm_cleanup(
        job_id,
        owner_id=f"job:{job_id}",
        ok=True,
    )


def run_job(storage_root: Path, job_id: str) -> None:
    storage = Storage(storage_root)
    try:
        with maintain_job_lease(
            storage.job_ledger,
            job_id,
            owner_id=f"job:{job_id}",
        ):
            if storage.job_ledger.cancel_requested(job_id):
                raise JobCancellationRequested(job_id)
            process_match(storage, job_id)
    except JobCancellationRequested:
        _confirm_cancelled(storage, job_id)
    except Exception as exc:  # pragma: no cover - exercised through API/job status
        if storage.job_ledger.cancel_requested(job_id):
            _confirm_cancelled(storage, job_id)
            return
        failure_message = str(exc) or "Processing failed"
        storage.update_job(job_id, status="failed", progress=1.0, message=failure_message, error=failure_message)
        match_id = storage.get_job(job_id).matchId
        storage.update_match_status(match_id, status="failed")
        traceback.print_exc()
    finally:
        storage.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Guerilla Analytics job worker.")
    parser.add_argument("--storage-root", required=True)
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()
    run_job(Path(args.storage_root), args.job_id)


if __name__ == "__main__":
    main()
