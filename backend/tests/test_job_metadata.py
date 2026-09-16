import sqlite3

from backend.app.schemas import MatchConfig
from backend.app.storage import Storage


def test_job_record_tracks_log_path_and_terminal_timestamps(tmp_path):
    storage = Storage(tmp_path)
    upload_path = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="trimmed-demo",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload_path,
        config=MatchConfig(autoHomography=True),
    )

    queued = storage.create_job(match.id)

    assert queued.logPath.endswith(f"logs/job_{queued.id}.log")
    assert queued.remoteRunId is None
    assert queued.startedAt is None
    assert queued.completedAt is None
    assert queued.durationSeconds is None

    processing = storage.update_job(
        queued.id,
        status="processing",
        progress=0.1,
        message="Loading input",
    )

    assert processing.startedAt is not None
    assert processing.completedAt is None
    assert processing.durationSeconds is None

    completed = storage.update_job(
        queued.id,
        status="completed",
        progress=1.0,
        message="Processing complete",
    )

    assert completed.startedAt is not None
    assert completed.completedAt is not None
    assert completed.durationSeconds is not None
    assert completed.durationSeconds >= 0


def test_job_record_persists_remote_run_id(tmp_path):
    storage = Storage(tmp_path)
    upload_path = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="trimmed-demo",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload_path,
        config=MatchConfig(autoHomography=True),
    )

    queued = storage.create_job(match.id)
    processing = storage.update_job(
        queued.id,
        status="processing",
        progress=0.25,
        message="Waiting for Runpod result",
        remote_run_id="runpod-123",
    )

    assert processing.remoteRunId == "runpod-123"
    assert storage.get_job(queued.id).remoteRunId == "runpod-123"

    with sqlite3.connect(storage.db_path) as connection:
        legacy_column_value = connection.execute(
            "SELECT runpod_run_id FROM jobs WHERE id = ?", (queued.id,)
        ).fetchone()[0]
        columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)")}

    assert legacy_column_value == "runpod-123"
    assert "runpod_run_id" in columns

    with sqlite3.connect(storage.db_path) as connection:
        connection.execute(
            "UPDATE jobs SET runpod_run_id = ? WHERE id = ?",
            ("legacy-direct-id", queued.id),
        )

    assert storage.get_job(queued.id).remoteRunId == "legacy-direct-id"
