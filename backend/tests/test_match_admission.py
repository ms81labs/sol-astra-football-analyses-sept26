from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path

import anyio
import httpx
import pytest

from backend.app.jobs import JobDispatchError, JobRunner
from backend.app.main import create_app
from backend.app.schemas import MatchConfig
from backend.app.storage import Storage


TOKEN = "upload-retry:one"


def _run(coro, *args):
    return anyio.run(coro, *args)


@asynccontextmanager
async def _client(tmp_path: Path):
    app = create_app(storage_root=tmp_path / "storage", run_jobs_inline=False)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://127.0.0.1",
    ) as client:
        yield app, client


def _request(*, token: str | None = TOKEN, payload: bytes = b"[]") -> dict:
    headers = {"Idempotency-Key": token} if token is not None else {}
    return {
        "headers": headers,
        "data": {
            "name": "Admission Test",
            "inputMode": "tracking_json",
            "config": "{}",
        },
        "files": {"file": ("tracking.json", payload, "application/json")},
    }


def _rows(storage: Storage) -> tuple[list[sqlite3.Row], list[sqlite3.Row]]:
    with storage._connect() as connection:
        matches = connection.execute("SELECT * FROM matches").fetchall()
        jobs = connection.execute("SELECT * FROM jobs").fetchall()
    return matches, jobs


def _uploads(storage: Storage) -> list[Path]:
    upload_dir = storage.storage_root / "uploads"
    return [] if not upload_dir.exists() else list(upload_dir.iterdir())


@pytest.mark.parametrize("table", ["matches", "jobs"])
def test_admission_insert_failure_rolls_back_pair_and_discards_only_its_upload(
    tmp_path: Path,
    table: str,
) -> None:
    storage = Storage(tmp_path)
    retained = storage.save_upload("retained.json", b"retained")
    candidate = storage.save_upload("candidate.json", b"candidate")
    with storage._connect() as connection:
        connection.execute(
            f"CREATE TRIGGER reject_admission BEFORE INSERT ON {table} "
            "BEGIN SELECT RAISE(FAIL, 'injected insert failure'); END"
        )

    with pytest.raises(sqlite3.IntegrityError, match="injected insert failure"):
        storage.admit_match_job(
            match_id="match-one",
            job_id="job-one",
            admission_token=TOKEN,
            name="Admission Test",
            input_mode="tracking_json",
            original_filename="candidate.json",
            input_path=candidate,
            config=MatchConfig(),
        )

    assert _rows(storage) == ([], [])
    assert _uploads(storage) == [retained]
    assert retained.read_bytes() == b"retained"


def test_admission_commit_failure_rolls_back_pair_and_discards_upload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = Storage(tmp_path)
    candidate = storage.save_upload("candidate.json", b"candidate")
    connect = storage._connect
    first = True

    class CommitFailure:
        def __init__(self, connection: sqlite3.Connection):
            self.connection = connection

        def __getattr__(self, name: str):
            return getattr(self.connection, name)

        def commit(self) -> None:
            raise sqlite3.OperationalError("injected commit failure")

    def connect_once():
        nonlocal first
        connection = connect()
        if first:
            first = False
            return CommitFailure(connection)
        return connection

    monkeypatch.setattr(storage, "_connect", connect_once)

    with pytest.raises(sqlite3.OperationalError, match="injected commit failure"):
        storage.admit_match_job(
            match_id="match-one",
            job_id="job-one",
            admission_token=TOKEN,
            name="Admission Test",
            input_mode="tracking_json",
            original_filename="candidate.json",
            input_path=candidate,
            config=MatchConfig(),
        )

    assert _rows(storage) == ([], [])
    assert _uploads(storage) == []


def test_admission_close_failure_after_commit_preserves_known_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = Storage(tmp_path)
    candidate = storage.save_upload("candidate.json", b"candidate")
    connect = storage._connect
    first = True

    class CloseFailureAfterCommit:
        def __init__(self, connection: sqlite3.Connection):
            self.connection = connection

        def __getattr__(self, name: str):
            return getattr(self.connection, name)

        def close(self) -> None:
            self.connection.close()
            raise sqlite3.OperationalError("injected close failure after commit")

    def connect_once():
        nonlocal first
        connection = connect()
        if first:
            first = False
            return CloseFailureAfterCommit(connection)
        return connection

    monkeypatch.setattr(storage, "_connect", connect_once)

    match, job, created = storage.admit_match_job(
        match_id="match-one",
        job_id="job-one",
        admission_token=TOKEN,
        name="Admission Test",
        input_mode="tracking_json",
        original_filename="candidate.json",
        input_path=candidate,
        config=MatchConfig(),
    )

    assert (match.id, job.id, created) == ("match-one", "job-one", True)
    assert _uploads(storage) == [candidate]


def test_commit_then_raise_recovers_admission_and_dispatches_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _run(_commit_then_raise_recovers_admission_and_dispatches_once, tmp_path, monkeypatch)


async def _commit_then_raise_recovers_admission_and_dispatches_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatches: list[str] = []
    monkeypatch.setattr(JobRunner, "start", lambda _runner, job_id: dispatches.append(job_id))
    async with _client(tmp_path) as (app, client):
        connect = app.state.storage._connect
        calls = 0

        class CommitThenRaise:
            def __init__(self, connection: sqlite3.Connection):
                self.connection = connection

            def __getattr__(self, name: str):
                return getattr(self.connection, name)

            def commit(self) -> None:
                self.connection.commit()
                raise sqlite3.OperationalError("injected error after commit")

        def connect_with_commit_fault():
            nonlocal calls
            calls += 1
            connection = connect()
            return CommitThenRaise(connection) if calls == 2 else connection

        monkeypatch.setattr(app.state.storage, "_connect", connect_with_commit_fault)
        response = await client.post("/api/matches", **_request())

        assert response.status_code == 202
        payload = response.json()
        assert payload["admissionToken"] == TOKEN
        assert payload["dispatchOutcome"] == "started"
        matches, jobs = _rows(app.state.storage)
        assert [row["id"] for row in matches] == [payload["matchId"]]
        assert [row["id"] for row in jobs] == [payload["jobId"]]
        assert dispatches == [payload["jobId"]]
        assert len(_uploads(app.state.storage)) == 1

        replay = await client.post("/api/matches", **_request(payload=b"ignored retry"))
        assert replay.status_code == 202
        assert replay.json()["matchId"] == payload["matchId"]
        assert replay.json()["jobId"] == payload["jobId"]
        assert dispatches == [payload["jobId"]]
        assert len(_uploads(app.state.storage)) == 1


def test_successful_admission_commits_preallocated_pair_and_exact_input_path(
    tmp_path: Path,
) -> None:
    storage = Storage(tmp_path)
    candidate = storage.save_upload("candidate.json", b"candidate")

    match, job, created = storage.admit_match_job(
        match_id="match-stable",
        job_id="job-stable",
        admission_token=TOKEN,
        name="Admission Test",
        input_mode="tracking_json",
        original_filename="candidate.json",
        input_path=candidate,
        config=MatchConfig(),
    )

    assert (match.id, job.id, created) == ("match-stable", "job-stable", True)
    assert (match.status, job.status, job.message) == (
        "processing",
        "dispatching",
        "Dispatching",
    )
    with storage._connect() as connection:
        row = connection.execute(
            "SELECT input_path, admission_token FROM matches WHERE id = ?",
            (match.id,),
        ).fetchone()
    assert dict(row) == {"input_path": str(candidate), "admission_token": TOKEN}


def test_post_commit_read_failure_returns_recovery_identity_and_preserves_admission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _run(
        _post_commit_read_failure_returns_recovery_identity_and_preserves_admission,
        tmp_path,
        monkeypatch,
    )


async def _post_commit_read_failure_returns_recovery_identity_and_preserves_admission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(JobRunner, "start", lambda *args: pytest.fail("read failure dispatched"))
    async with _client(tmp_path) as (app, client):
        monkeypatch.setattr(
            app.state.storage,
            "get_match",
            lambda *args: (_ for _ in ()).throw(
                sqlite3.OperationalError("injected post-commit read failure")
            ),
        )
        response = await client.post("/api/matches", **_request())

        assert response.status_code == 503
        detail = response.json()["detail"]
        assert detail["code"] == "admission_outcome_uncertain"
        assert detail["matchId"]
        assert detail["jobId"]
        assert detail["admissionToken"] == TOKEN
        matches, jobs = _rows(app.state.storage)
        assert [(row["id"], row["admission_token"]) for row in matches] == [
            (detail["matchId"], TOKEN)
        ]
        assert [row["id"] for row in jobs] == [detail["jobId"]]
        assert len(_uploads(app.state.storage)) == 1


def test_admission_reuses_token_and_discards_losing_upload(tmp_path: Path) -> None:
    storage = Storage(tmp_path)
    winner = storage.save_upload("winner.json", b"winner")
    first = storage.admit_match_job(
        match_id="match-winner",
        job_id="job-winner",
        admission_token=TOKEN,
        name="Winner",
        input_mode="tracking_json",
        original_filename="winner.json",
        input_path=winner,
        config=MatchConfig(),
    )
    loser = storage.save_upload("loser.json", b"loser")

    second = storage.admit_match_job(
        match_id="match-loser",
        job_id="job-loser",
        admission_token=TOKEN,
        name="Ignored retry metadata",
        input_mode="video",
        original_filename="loser.json",
        input_path=loser,
        config=MatchConfig(autoHomography=True),
    )

    assert first[2] is True
    assert (second[0].id, second[1].id, second[2]) == (
        "match-winner",
        "job-winner",
        False,
    )
    assert _uploads(storage) == [winner]
    assert len(_rows(storage)[0]) == len(_rows(storage)[1]) == 1


def test_invalid_token_fails_before_upload_or_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _run(_invalid_token_fails_before_upload_or_dispatch, tmp_path, monkeypatch)


async def _invalid_token_fails_before_upload_or_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        Storage,
        "save_upload_stream",
        lambda *args, **kwargs: pytest.fail("invalid token wrote an upload"),
    )
    monkeypatch.setattr(
        JobRunner,
        "start",
        lambda *args, **kwargs: pytest.fail("invalid token dispatched"),
    )
    async with _client(tmp_path) as (app, client):
        for token in ("", "space is invalid", "x" * 129, "slash/invalid"):
            response = await client.post("/api/matches", **_request(token=token))
            assert response.status_code == 400
        assert _rows(app.state.storage) == ([], [])
        assert _uploads(app.state.storage) == []


def test_caller_token_replays_lost_response_before_upload_or_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _run(_caller_token_replays_lost_response_before_upload_or_dispatch, tmp_path, monkeypatch)


async def _caller_token_replays_lost_response_before_upload_or_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with _client(tmp_path) as (app, client):
        dispatches: list[str] = []

        def observe_dispatch(_runner: JobRunner, job_id: str) -> None:
            assert app.state.storage.get_job(job_id).status == "dispatching"
            dispatches.append(job_id)

        monkeypatch.setattr(JobRunner, "start", observe_dispatch)
        first = await client.post("/api/matches", **_request(payload=b"first"))
        assert first.status_code == 202
        first_payload = first.json()
        assert first_payload["status"] == "queued"
        assert first_payload["dispatchOutcome"] == "started"
        assert first_payload["admissionToken"] == TOKEN
        assert first_payload["reused"] is False

        monkeypatch.setattr(
            app.state.storage,
            "save_upload_stream",
            lambda *args, **kwargs: pytest.fail("retry read or wrote its upload"),
        )
        replay = await client.post(
            "/api/matches",
            **_request(payload=b"different ignored body"),
        )

        assert replay.status_code == 202
        assert replay.json() == {
            **first_payload,
            "dispatchOutcome": "reused",
            "reused": True,
        }
        assert dispatches == [first_payload["jobId"]]
        assert len(_uploads(app.state.storage)) == 1


def test_token_replay_ignores_repeated_multipart_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _run(_token_replay_ignores_repeated_multipart_metadata, tmp_path, monkeypatch)


async def _token_replay_ignores_repeated_multipart_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatches: list[str] = []
    monkeypatch.setattr(JobRunner, "start", lambda _runner, job_id: dispatches.append(job_id))
    async with _client(tmp_path) as (app, client):
        first = await client.post("/api/matches", **_request())
        replay_request = _request(payload=b"ignored")
        replay_request["data"] = {
            "name": "ignored",
            "inputMode": "invalid-on-replay",
            "config": "not-json",
        }
        replay = await client.post("/api/matches", **replay_request)

        assert replay.status_code == 202
        assert replay.json()["matchId"] == first.json()["matchId"]
        assert replay.json()["dispatchOutcome"] == "reused"
        assert dispatches == [first.json()["jobId"]]
        assert len(_uploads(app.state.storage)) == 1


def test_concurrent_same_token_requests_converge_and_clean_losing_upload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _run(_concurrent_same_token_requests_converge_and_clean_losing_upload, tmp_path, monkeypatch)


async def _concurrent_same_token_requests_converge_and_clean_losing_upload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatches: list[str] = []
    monkeypatch.setattr(JobRunner, "start", lambda _runner, job_id: dispatches.append(job_id))
    async with _client(tmp_path) as (app, client):
        saved = app.state.storage.save_upload_stream
        barrier = threading.Barrier(2)

        def synchronize_upload(*args, **kwargs):
            path = saved(*args, **kwargs)
            barrier.wait(timeout=5)
            return path

        monkeypatch.setattr(app.state.storage, "save_upload_stream", synchronize_upload)
        responses: list[httpx.Response] = []

        async def upload(payload: bytes) -> None:
            responses.append(await client.post("/api/matches", **_request(payload=payload)))

        async with anyio.create_task_group() as group:
            group.start_soon(upload, b"first")
            group.start_soon(upload, b"second")

        payloads = [response.json() for response in responses]
        assert [response.status_code for response in responses] == [202, 202]
        assert {payload["matchId"] for payload in payloads} == {payloads[0]["matchId"]}
        assert {payload["jobId"] for payload in payloads} == {payloads[0]["jobId"]}
        assert sorted(payload["reused"] for payload in payloads) == [False, True]
        assert dispatches == [payloads[0]["jobId"]]
        assert len(_uploads(app.state.storage)) == 1
        assert len(_rows(app.state.storage)[0]) == len(_rows(app.state.storage)[1]) == 1


@pytest.mark.parametrize(
    ("child_may_have_started", "outcome", "expected_error"),
    [
        (False, "failed", "Job dispatch failed before processing started."),
        (
            True,
            "uncertain",
            "Job dispatch outcome is uncertain; automatic retry is disabled.",
        ),
    ],
)
def test_dispatch_failure_is_accepted_visible_and_never_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    child_may_have_started: bool,
    outcome: str,
    expected_error: str,
) -> None:
    _run(
        _dispatch_failure_is_accepted_visible_and_never_retried,
        tmp_path,
        monkeypatch,
        child_may_have_started,
        outcome,
        expected_error,
    )


async def _dispatch_failure_is_accepted_visible_and_never_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    child_may_have_started: bool,
    outcome: str,
    expected_error: str,
) -> None:
    dispatches: list[str] = []

    def fail_dispatch(_runner: JobRunner, job_id: str) -> None:
        dispatches.append(job_id)
        raise JobDispatchError(
            "provider-secret-should-not-escape",
            child_may_have_started=child_may_have_started,
        )

    monkeypatch.setattr(JobRunner, "start", fail_dispatch)
    async with _client(tmp_path) as (app, client):
        response = await client.post("/api/matches", **_request())
        assert response.status_code == 202
        payload = response.json()
        assert payload["dispatchOutcome"] == outcome
        assert payload["status"] == "failed"
        assert payload["admissionToken"] == TOKEN
        assert payload["reused"] is False
        match = app.state.storage.get_match(payload["matchId"])
        job = app.state.storage.get_job(payload["jobId"])
        assert match.status == job.status == "failed"
        assert job.error == expected_error
        assert "provider-secret" not in json.dumps(payload)
        assert len(_uploads(app.state.storage)) == 1

        replay = await client.post("/api/matches", **_request(payload=b"retry"))
        assert replay.status_code == 202
        assert replay.json()["dispatchOutcome"] == "reused"
        assert dispatches == [payload["jobId"]]
        assert len(_uploads(app.state.storage)) == 1


def test_late_inline_dispatch_error_makes_processing_admission_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _run(_late_inline_dispatch_error_makes_processing_admission_terminal, tmp_path, monkeypatch)


async def _late_inline_dispatch_error_makes_processing_admission_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with _client(tmp_path) as (app, client):
        def start_then_fail(_runner: JobRunner, job_id: str) -> None:
            app.state.storage.update_job(
                job_id,
                status="processing",
                progress=0.1,
                message="Processing",
            )
            raise JobDispatchError("late failure", child_may_have_started=True)

        monkeypatch.setattr(JobRunner, "start", start_then_fail)
        response = await client.post("/api/matches", **_request())

        assert response.status_code == 202
        payload = response.json()
        assert payload["dispatchOutcome"] == "uncertain"
        assert payload["status"] == "failed"
        assert app.state.storage.get_job(payload["jobId"]).status == "failed"
        assert app.state.storage.get_match(payload["matchId"]).status == "failed"


def test_late_dispatch_error_does_not_overwrite_completed_worker_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _run(_late_dispatch_error_does_not_overwrite_completed_worker_state, tmp_path, monkeypatch)


async def _late_dispatch_error_does_not_overwrite_completed_worker_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with _client(tmp_path) as (app, client):
        def complete_then_fail(_runner: JobRunner, job_id: str) -> None:
            match_id = app.state.storage.get_job(job_id).matchId
            app.state.storage.update_match_status(match_id, status="ready")
            app.state.storage.update_job(
                job_id,
                status="completed",
                progress=1.0,
                message="Completed",
            )
            raise JobDispatchError("late failure", child_may_have_started=True)

        monkeypatch.setattr(JobRunner, "start", complete_then_fail)
        response = await client.post("/api/matches", **_request())

        assert response.status_code == 202
        payload = response.json()
        assert payload["status"] == "completed"
        assert app.state.storage.get_job(payload["jobId"]).status == "completed"
        assert app.state.storage.get_match(payload["matchId"]).status == "ready"


def test_dispatch_status_write_failure_preserves_dispatching_admission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _run(_dispatch_status_write_failure_preserves_dispatching_admission, tmp_path, monkeypatch)


async def _dispatch_status_write_failure_preserves_dispatching_admission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatches: list[str] = []

    def fail_dispatch(_runner: JobRunner, job_id: str) -> None:
        dispatches.append(job_id)
        raise JobDispatchError("known failure", child_may_have_started=False)

    monkeypatch.setattr(JobRunner, "start", fail_dispatch)
    async with _client(tmp_path) as (app, client):
        monkeypatch.setattr(
            app.state.storage,
            "mark_dispatch_failed",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                sqlite3.OperationalError("injected status write failure")
            ),
        )
        response = await client.post("/api/matches", **_request())
        assert response.status_code == 202
        payload = response.json()
        assert payload["dispatchOutcome"] == "failed"
        assert payload["status"] == "dispatching"
        match = app.state.storage.get_match(payload["matchId"])
        job = app.state.storage.get_job(payload["jobId"])
        assert match.status == "processing"
        assert job.status == "dispatching"
        assert len(_uploads(app.state.storage)) == 1

        replay = await client.post("/api/matches", **_request(payload=b"retry"))
        assert replay.status_code == 202
        assert replay.json()["dispatchOutcome"] == "reused"
        assert dispatches == [payload["jobId"]]


def test_successful_start_keeps_started_outcome_when_mark_dispatched_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _run(
        _successful_start_keeps_started_outcome_when_mark_dispatched_fails,
        tmp_path,
        monkeypatch,
    )


async def _successful_start_keeps_started_outcome_when_mark_dispatched_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with _client(tmp_path) as (app, client):
        def start_processing(_runner: JobRunner, job_id: str) -> None:
            app.state.storage.update_job(
                job_id,
                status="processing",
                progress=0.1,
                message="Processing",
            )

        monkeypatch.setattr(JobRunner, "start", start_processing)
        monkeypatch.setattr(
            app.state.storage,
            "mark_dispatched",
            lambda *args: (_ for _ in ()).throw(
                sqlite3.OperationalError("injected post-start status failure")
            ),
        )
        monkeypatch.setattr(
            app.state.storage,
            "mark_dispatch_failed",
            lambda *args, **kwargs: pytest.fail("successful start was marked failed"),
        )
        response = await client.post("/api/matches", **_request())

        assert response.status_code == 202
        payload = response.json()
        assert payload["dispatchOutcome"] == "started"
        assert payload["status"] == "dispatching"
        assert app.state.storage.get_job(payload["jobId"]).status == "processing"
        assert app.state.storage.get_match(payload["matchId"]).status == "processing"


def test_committed_dispatch_failure_read_error_still_returns_accepted_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _run(
        _committed_dispatch_failure_read_error_still_returns_accepted_snapshot,
        tmp_path,
        monkeypatch,
    )


async def _committed_dispatch_failure_read_error_still_returns_accepted_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        JobRunner,
        "start",
        lambda *_args: (_ for _ in ()).throw(
            JobDispatchError("known failure", child_may_have_started=False)
        ),
    )
    async with _client(tmp_path) as (app, client):
        persisted = app.state.storage.mark_dispatch_failed

        def persist_without_read(*args, **kwargs):
            monkeypatch.setattr(
                app.state.storage,
                "get_job",
                lambda *_args: (_ for _ in ()).throw(
                    sqlite3.OperationalError("injected post-commit read failure")
                ),
            )
            return persisted(*args, **kwargs)

        monkeypatch.setattr(app.state.storage, "mark_dispatch_failed", persist_without_read)
        response = await client.post("/api/matches", **_request())

        assert response.status_code == 202
        payload = response.json()
        assert payload["dispatchOutcome"] == "failed"
        assert payload["status"] == "dispatching"
        assert payload["admissionToken"] == TOKEN
        matches, jobs = _rows(app.state.storage)
        assert [row["id"] for row in matches] == [payload["matchId"]]
        assert [row["id"] for row in jobs] == [payload["jobId"]]
        assert matches[0]["status"] == jobs[0]["status"] == "failed"
        assert jobs[0]["error"] == "Job dispatch failed before processing started."
        assert len(_uploads(app.state.storage)) == 1


def test_different_tokens_create_independent_admissions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _run(_different_tokens_create_independent_admissions, tmp_path, monkeypatch)


async def _different_tokens_create_independent_admissions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatches: list[str] = []
    monkeypatch.setattr(JobRunner, "start", lambda _runner, job_id: dispatches.append(job_id))
    async with _client(tmp_path) as (app, client):
        first = await client.post("/api/matches", **_request(token="token-one"))
        second = await client.post("/api/matches", **_request(token="token-two"))

        assert first.status_code == second.status_code == 202
        assert first.json()["matchId"] != second.json()["matchId"]
        assert first.json()["jobId"] != second.json()["jobId"]
        assert len(dispatches) == 2
        assert len(_rows(app.state.storage)[0]) == len(_rows(app.state.storage)[1]) == 2
        assert len(_uploads(app.state.storage)) == 2
