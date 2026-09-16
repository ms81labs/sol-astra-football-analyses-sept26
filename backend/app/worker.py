from __future__ import annotations

import argparse
import traceback
from pathlib import Path

from .processor import process_match
from .storage import Storage


def run_job(storage_root: Path, job_id: str) -> None:
    storage = Storage(storage_root)
    try:
        process_match(storage, job_id)
    except Exception as exc:  # pragma: no cover - exercised through API/job status
        failure_message = str(exc) or "Processing failed"
        storage.update_job(job_id, status="failed", progress=1.0, message=failure_message, error=failure_message)
        match_id = storage.get_job(job_id).matchId
        storage.update_match_status(match_id, status="failed")
        traceback.print_exc()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Guerilla Analytics job worker.")
    parser.add_argument("--storage-root", required=True)
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()
    run_job(Path(args.storage_root), args.job_id)


if __name__ == "__main__":
    main()
