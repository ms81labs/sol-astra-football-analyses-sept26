from __future__ import annotations

import threading
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

import anyio
import httpx
import pytest

from backend.app.jobs import JobRunner
from backend.app.main import create_app
from backend.app.schemas import MatchConfig


def _run(coro, *args) -> None:
    anyio.run(coro, *args)


@asynccontextmanager
async def _client(tmp_path: Path, *, run_jobs_inline: bool = False):
    app = create_app(storage_root=tmp_path / "storage", run_jobs_inline=run_jobs_inline)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        yield app, client


@contextmanager
def _bounded_block(release: threading.Event):
    timed_out = threading.Event()

    def release_on_timeout() -> None:
        timed_out.set()
        release.set()

    timer = threading.Timer(4.0, release_on_timeout)
    timer.start()
    try:
        yield timed_out
    finally:
        release.set()
        timer.cancel()
        timer.join()


async def _wait_for(event: threading.Event) -> None:
    assert await anyio.to_thread.run_sync(event.wait, 2.0), "blocked operation was not entered"


async def _websocket_probe(app, path: str) -> list[dict]:
    messages: list[dict] = []
    connected = False

    async def receive() -> dict:
        nonlocal connected
        if not connected:
            connected = True
            return {"type": "websocket.connect"}
        await anyio.sleep_forever()

    async def send(message: dict) -> None:
        messages.append(message)

    await app(
        {
            "type": "websocket",
            "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1",
            "scheme": "ws",
            "server": ("127.0.0.1", 80),
            "client": ("127.0.0.1", 50000),
            "root_path": "",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [(b"host", b"127.0.0.1")],
            "subprotocols": [],
            "state": {},
        },
        receive,
        send,
    )
    return messages


def test_frames_read_does_not_block_other_http_requests(tmp_path: Path, monkeypatch) -> None:
    _run(_test_frames_read_does_not_block_other_http_requests, tmp_path, monkeypatch)


async def _test_frames_read_does_not_block_other_http_requests(tmp_path: Path, monkeypatch) -> None:
    entered = threading.Event()
    release = threading.Event()
    worker_threads: list[int] = []
    event_loop_thread = threading.get_ident()

    async with _client(tmp_path) as (app, client):
        match = app.state.storage.create_match(
            "Held", "tracking_json", "tracking.json", tmp_path / "tracking.json", MatchConfig()
        )

        def blocked_load_frames(_match_id: str):
            worker_threads.append(threading.get_ident())
            entered.set()
            assert release.wait(4.0)
            return []

        monkeypatch.setattr(app.state.storage, "load_frames", blocked_load_frames)
        held_response: dict[str, httpx.Response] = {}

        async def request_frames() -> None:
            held_response["response"] = await client.get(f"/api/matches/{match.id}/frames")

        with _bounded_block(release) as timed_out, anyio.fail_after(5.0):
            async with anyio.create_task_group() as tasks:
                tasks.start_soon(request_frames)
                await _wait_for(entered)
                lightweight = await client.get("/api/bundles")
                assert lightweight.status_code == 200
                assert not timed_out.is_set(), "lightweight request waited for the blocked frames read"
                release.set()

        assert held_response["response"].status_code == 200
        assert worker_threads == [worker_threads[0]]
        assert worker_threads[0] != event_loop_thread


@pytest.mark.parametrize(
    ("analysis_result", "expected_status"),
    [({"ok": True}, 200), (RuntimeError("analysis exploded"), 400)],
)
def test_analysis_does_not_block_http_or_websocket_progress(
    tmp_path: Path,
    monkeypatch,
    analysis_result,
    expected_status: int,
) -> None:
    _run(
        _test_analysis_does_not_block_http_or_websocket_progress,
        tmp_path,
        monkeypatch,
        analysis_result,
        expected_status,
    )


async def _test_analysis_does_not_block_http_or_websocket_progress(
    tmp_path: Path,
    monkeypatch,
    analysis_result,
    expected_status: int,
) -> None:
    entered = threading.Event()
    release = threading.Event()
    worker_threads: list[int] = []
    event_loop_thread = threading.get_ident()

    async with _client(tmp_path) as (app, client):
        match = app.state.storage.create_match(
            "Concurrency", "tracking_json", "tracking.json", tmp_path / "tracking.json", MatchConfig()
        )
        monkeypatch.setattr(app.state.storage, "load_frames", lambda _match_id: [])

        def blocked_analysis(*_args, **_kwargs):
            worker_threads.append(threading.get_ident())
            entered.set()
            assert release.wait(4.0)
            if isinstance(analysis_result, Exception):
                raise analysis_result
            return analysis_result

        monkeypatch.setattr("backend.app.main.run_analysis", blocked_analysis)
        responses: dict[str, object] = {}

        async def request_analysis() -> None:
            responses["analysis"] = await client.post(
                f"/api/matches/{match.id}/analysis/snapshot",
                json={"provider": "local"},
            )

        async def probe_websocket() -> None:
            responses["websocket"] = await _websocket_probe(app, "/ws/jobs/missing")

        with _bounded_block(release) as timed_out, anyio.fail_after(5.0):
            async with anyio.create_task_group() as tasks:
                tasks.start_soon(request_analysis)
                await _wait_for(entered)
                tasks.start_soon(probe_websocket)
                lightweight = await client.get("/api/bundles")
                assert lightweight.status_code == 200
                with anyio.fail_after(0.5):
                    while "websocket" not in responses:
                        await anyio.sleep(0)
                assert not timed_out.is_set(), "HTTP/websocket progress waited for analysis"
                release.set()

        analysis_response = responses["analysis"]
        assert isinstance(analysis_response, httpx.Response)
        assert analysis_response.status_code == expected_status
        if expected_status == 200:
            assert analysis_response.json().items() >= analysis_result.items()
        else:
            assert analysis_response.json() == {"detail": str(analysis_result)}
        websocket_messages = responses["websocket"]
        assert isinstance(websocket_messages, list)
        assert {"type": "websocket.send", "text": '{"error":"Job not found"}'} in websocket_messages
        assert worker_threads[0] != event_loop_thread


def test_inline_upload_dispatch_does_not_block_other_http_requests(tmp_path: Path, monkeypatch) -> None:
    _run(_test_inline_upload_dispatch_does_not_block_other_http_requests, tmp_path, monkeypatch)


async def _test_inline_upload_dispatch_does_not_block_other_http_requests(tmp_path: Path, monkeypatch) -> None:
    entered = threading.Event()
    release = threading.Event()
    worker_threads: list[int] = []
    event_loop_thread = threading.get_ident()

    def blocked_start(runner: JobRunner, _job_id: str) -> None:
        assert runner.run_jobs_inline is True
        worker_threads.append(threading.get_ident())
        entered.set()
        assert release.wait(4.0)

    monkeypatch.setattr(JobRunner, "start", blocked_start)
    async with _client(tmp_path, run_jobs_inline=True) as (_, client):
        upload_response: dict[str, httpx.Response] = {}

        async def upload() -> None:
            upload_response["response"] = await client.post(
                "/api/matches",
                headers={"Idempotency-Key": "concurrency:inline-dispatch"},
                data={"name": "Concurrency", "inputMode": "tracking_json", "config": "{}"},
                files={"file": ("tracking.json", b"[]", "application/json")},
            )

        with _bounded_block(release) as timed_out, anyio.fail_after(5.0):
            async with anyio.create_task_group() as tasks:
                tasks.start_soon(upload)
                await _wait_for(entered)
                lightweight = await client.get("/api/bundles")
                assert lightweight.status_code == 200
                assert not timed_out.is_set(), "lightweight request waited for inline dispatch"
                release.set()

        response = upload_response["response"]
        assert response.status_code == 202
        assert response.json()["dispatchOutcome"] == "started"
        assert response.json()["reused"] is False
        assert worker_threads[0] != event_loop_thread


def test_websocket_job_read_does_not_block_http_requests(tmp_path: Path, monkeypatch) -> None:
    _run(_test_websocket_job_read_does_not_block_http_requests, tmp_path, monkeypatch)


async def _test_websocket_job_read_does_not_block_http_requests(tmp_path: Path, monkeypatch) -> None:
    entered = threading.Event()
    release = threading.Event()
    worker_threads: list[int] = []
    event_loop_thread = threading.get_ident()

    async with _client(tmp_path) as (app, client):
        storage = app.state.storage
        input_path = storage.save_upload("tracking.json", b"[]")
        match = storage.create_match("Concurrency", "tracking_json", "tracking.json", input_path, MatchConfig())
        job = storage.create_job(match.id)
        storage.update_job(job.id, status="completed", progress=100, message="Done")
        get_job = storage.get_job

        def blocked_get_job(job_id: str):
            worker_threads.append(threading.get_ident())
            entered.set()
            assert release.wait(4.0)
            return get_job(job_id)

        monkeypatch.setattr(storage, "get_job", blocked_get_job)
        websocket_result: dict[str, list[dict]] = {}

        async def probe_websocket() -> None:
            websocket_result["messages"] = await _websocket_probe(app, f"/ws/jobs/{job.id}")

        with _bounded_block(release) as timed_out, anyio.fail_after(5.0):
            async with anyio.create_task_group() as tasks:
                tasks.start_soon(probe_websocket)
                await _wait_for(entered)
                lightweight = await client.get("/api/bundles")
                assert lightweight.status_code == 200
                assert not timed_out.is_set(), "lightweight request waited for websocket storage"
                release.set()

        messages = websocket_result["messages"]
        assert messages[0]["type"] == "websocket.accept"
        assert messages[-1]["type"] == "websocket.close"
        assert any(job.id in message.get("text", "") for message in messages)
        assert worker_threads[0] != event_loop_thread
