from __future__ import annotations

import hashlib
import json
import os
import shlex
import sys
import threading
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

import pytest

from backend.app.remote_contracts import (
    CompletionReceipt,
    FileEntry,
    JobReceipt,
    JobRequest,
    ProgressEvent,
    ResultBundle,
    canonical_json_bytes,
)
from backend.app.gpu_worker import LIVE_PROGRESS_PREFIX
from backend.release.daytona_policy import load_daytona_policy
from backend.release.preflight import PreflightResult


COMMIT = "b" * 40
GENERATION = "0123456789abcdef0123456789abcdef"
EVENT_1 = ProgressEvent(
    1, "job-1", 1, 35, "trackingPass", "running",
    datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc),
)
EVENT_2 = ProgressEvent(
    1, "job-1", 2, 55, "probeObservedPass", "running",
    datetime(2026, 8, 24, 12, 1, tzinfo=timezone.utc),
)


def _entry(role: str, path: str, payload: bytes) -> FileEntry:
    return FileEntry(role, PurePosixPath(path), len(payload), hashlib.sha256(payload).hexdigest())


def _bundle(tmp_path: Path):
    root = tmp_path / "bundle"
    workspace = tmp_path / "workspace"
    root.mkdir()
    workspace.mkdir()
    request = JobRequest(1, "job-1", "match-1", PurePosixPath("sealed/receipt.json"), PurePosixPath("inputs/match.mp4"), {})
    payloads = {
        "source/source.tar": b"source",
        "manifest.json": b"manifest",
        "evidence.json": b"evidence",
        "models/model.bin": b"model",
        "inputs/match.mp4": b"video",
        "job-request.json": canonical_json_bytes(request.to_mapping()),
    }
    receipt = JobReceipt(
        1, COMMIT, hashlib.sha256(payloads["manifest.json"]).hexdigest(),
        hashlib.sha256(payloads["evidence.json"]).hexdigest(),
        hashlib.sha256(payloads["job-request.json"]).hexdigest(), request.config,
        tuple(_entry(role, path, payloads[path]) for role, path in (
            ("source_archive", "source/source.tar"), ("manifest", "manifest.json"),
            ("evidence", "evidence.json"), ("input_video", "inputs/match.mp4"),
            ("runtime_artifact", "models/model.bin"),
            ("job_request", "job-request.json"),
        )),
    )
    payloads["sealed/receipt.json"] = canonical_json_bytes(receipt.to_mapping())
    for relative, payload in payloads.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    runtime = root / "models/model.bin"
    preflight = PreflightResult(
        COMMIT, receipt.manifest_sha256, root / "manifest.json", root / "evidence.json", "pre_cloud",
        receipt.evidence_sha256, (("model", runtime, "/app/models/model.bin"),),
        (("model", hashlib.sha256(b"model").hexdigest(), len(b"model")),),
    )
    processor = b'{"detections":[]}'
    progress = b""
    namespace = f"result-bundle.json.generations/{GENERATION}"
    result = ResultBundle(
        1, request.job_id, request.match_id, COMMIT, receipt.manifest_sha256,
        hashlib.sha256(payloads["sealed/receipt.json"]).hexdigest(), receipt.requested_runtime_options,
        {"processorResultPath": f"{namespace}/result.processor-result.json", "progressPath": f"{namespace}/result.progress.jsonl", "progressEventCount": 0},
        (_entry("result_artifact", f"{namespace}/result.processor-result.json", processor),
         _entry("result_artifact", f"{namespace}/result.progress.jsonl", progress)),
    )
    result_bytes = canonical_json_bytes(result.to_mapping())
    completion = CompletionReceipt(
        1, request.job_id, request.match_id, PurePosixPath(f"{namespace}/result.json"),
        len(result_bytes), hashlib.sha256(result_bytes).hexdigest(), COMMIT, receipt.manifest_sha256,
        datetime(2026, 8, 24, 12, 30, tzinfo=timezone.utc),
    )
    remote = {
        "/home/daytona/job/completion-receipt.json": canonical_json_bytes(completion.to_mapping()),
        f"/home/daytona/job/{namespace}/result.json": result_bytes,
        f"/home/daytona/job/{namespace}/result.processor-result.json": processor,
        f"/home/daytona/job/{namespace}/result.progress.jsonl": progress,
    }
    return root, workspace, preflight, request, receipt, result, completion, remote


class _Response:
    def __init__(self, exit_code=0, result="ok"):
        self.exit_code = exit_code
        self.result = result


class _FS:
    def __init__(self, remote, fail_upload=False, fail_download=None):
        self.remote = remote
        self.uploads = []
        self.downloads = []
        self.fail_upload = fail_upload
        self.fail_download = fail_download

    def upload_file_stream(self, source, remote_path, timeout):
        if self.fail_upload:
            raise RuntimeError("upload token=secret")
        self.uploads.append((remote_path, source.read(), timeout))

    def download_file_stream(self, remote_path, timeout):
        self.downloads.append((remote_path, timeout))
        if remote_path == self.fail_download:
            raise RuntimeError("https://host/file?X-Amz-Signature=secret")
        if remote_path not in self.remote:
            raise FileNotFoundError(remote_path)
        return iter((self.remote[remote_path],))


class _Process:
    def __init__(
        self,
        response=None,
        error=None,
        session_states=None,
        *,
        create_error=None,
        status_error=None,
        logs_error=None,
        delete_error=None,
    ):
        self.response = response or _Response()
        self.error = error
        self.create_error = create_error
        self.status_error = status_error
        self.logs_error = logs_error
        self.delete_error = delete_error
        self.session_states = session_states or [
            (self.response.exit_code, self.response.result)
        ]
        self.session_index = 0
        self.created_sessions = []
        self.commands = []
        self.status_calls = []
        self.log_calls = []
        self.deleted_sessions = []
        self.delete_timeouts = []

    def create_session(self, session_id, request_timeout=None):
        self.created_sessions.append((session_id, request_timeout))
        if self.create_error:
            raise self.create_error

    def execute_session_command(self, session_id, request, timeout=None):
        self.commands.append((session_id, request, timeout))
        if self.error:
            raise self.error
        return SimpleNamespace(cmd_id="cmd-1")

    def get_session_command(self, session_id, command_id, request_timeout=None):
        self.status_calls.append((session_id, command_id, request_timeout))
        if self.status_error:
            raise self.status_error
        return SimpleNamespace(exit_code=self.session_states[self.session_index][0])

    def get_session_command_logs(self, session_id, command_id, request_timeout=None):
        self.log_calls.append((session_id, command_id, request_timeout))
        if self.logs_error:
            raise self.logs_error
        logs = SimpleNamespace(stdout=self.session_states[self.session_index][1])
        if self.session_index + 1 < len(self.session_states):
            self.session_index += 1
        return logs

    def delete_session(self, session_id, request_timeout=None):
        self.deleted_sessions.append(session_id)
        self.delete_timeouts.append(request_timeout)
        if self.delete_error:
            raise self.delete_error


class _Sandbox:
    def __init__(self, remote, *, sandbox_id="sb-123", **kwargs):
        self.id = sandbox_id
        self.fs = _FS(remote, kwargs.get("fail_upload", False), kwargs.get("fail_download"))
        self.process = kwargs.get("process") or _Process(
            kwargs.get("response"), kwargs.get("process_error")
        )


class _Client:
    def __init__(self, sandbox, *, create_error=None, delete_errors=()):
        self.sandbox = sandbox
        self.create_error = create_error
        self.create_calls = []
        self.delete_calls = []
        self.delete_errors = list(delete_errors)

    def create(self, spec, timeout):
        self.create_calls.append((spec, timeout))
        if self.create_error:
            raise self.create_error
        return self.sandbox

    def delete(self, sandbox, timeout, wait):
        self.delete_calls.append((sandbox, timeout, wait))
        if self.delete_errors:
            raise self.delete_errors.pop(0)


def _execution(tmp_path, *, remote_mutator=None, **sandbox_kwargs):
    from backend.app.daytona import DaytonaExecutionRequest

    root, workspace, preflight, request, receipt, result, completion, remote = _bundle(tmp_path)
    if remote_mutator:
        remote_mutator(remote)
    sandbox = _Sandbox(remote, **sandbox_kwargs)
    client = _Client(sandbox)
    calls = []
    def factory(api_key, target):
        calls.append((api_key, target))
        return client
    execution = DaytonaExecutionRequest("daytona-secret-value", load_daytona_policy(), root, workspace, preflight)
    return execution, client, sandbox, calls, (request, receipt, result, completion)


def test_remote_worker_import_does_not_import_daytona_sdk():
    sys.modules.pop("backend.app.remote_worker", None)
    sys.modules.pop("backend.app.daytona", None)
    before = {name for name in sys.modules if name == "daytona" or name.startswith("daytona.")}

    __import__("backend.app.remote_worker")

    after = {name for name in sys.modules if name == "daytona" or name.startswith("daytona.")}
    assert after == before


def test_execution_request_hides_api_key_and_is_frozen(tmp_path):
    from backend.app.daytona import DaytonaExecutionRequest

    request = DaytonaExecutionRequest(
        api_key="daytona-secret-value",
        policy=load_daytona_policy(),
        bundle_root=tmp_path,
        workspace=tmp_path,
        preflight=PreflightResult("b" * 40, "a" * 64, tmp_path, tmp_path, "final", "c" * 64, (), ()),
    )

    assert "daytona-secret-value" not in repr(request)
    with pytest.raises((AttributeError, TypeError)):
        request.api_key = "changed"  # type: ignore[misc]


def test_execution_command_keeps_outputs_inside_the_uploaded_job_root():
    from backend.app.daytona import EXECUTION_COMMAND, INPUT_ROOT, OUTPUT_ROOT

    arguments = shlex.split(EXECUTION_COMMAND)
    request_path = PurePosixPath(arguments[arguments.index("--request") + 1])
    result_path = PurePosixPath(arguments[arguments.index("--result") + 1])
    completion_path = PurePosixPath(arguments[arguments.index("--completion-receipt") + 1])

    assert PurePosixPath(INPUT_ROOT) == request_path.parent
    assert OUTPUT_ROOT == INPUT_ROOT
    assert result_path.is_relative_to(request_path.parent)
    assert completion_path.is_relative_to(request_path.parent)
    assert PurePosixPath(OUTPUT_ROOT).is_relative_to(request_path.parent)


def test_session_delivers_each_valid_progress_event_before_completion(tmp_path):
    from backend.app.daytona import execute_daytona_job

    first = LIVE_PROGRESS_PREFIX + canonical_json_bytes(EVENT_1.to_mapping()).decode()
    second = LIVE_PROGRESS_PREFIX + canonical_json_bytes(EVENT_2.to_mapping()).decode()
    process = _Process(session_states=[(None, first), (None, first + second), (0, first + second)])
    execution, client, _, _, _ = _execution(tmp_path, process=process)
    seen = []
    during_running = []

    execute_daytona_job(
        execution,
        client_factory=lambda *_: client,
        progress_callback=seen.append,
        poll_wait=lambda: during_running.append(tuple(seen)),
    )

    assert during_running == [(EVENT_1,), (EVENT_1, EVENT_2)]
    assert seen == [EVENT_1, EVENT_2]
    assert process.deleted_sessions == ["fa-job-1"]


def test_invalid_progress_logs_do_not_abort_a_successful_command(tmp_path):
    from backend.app.daytona import execute_daytona_job

    process = _Process(session_states=[(0, f"{LIVE_PROGRESS_PREFIX}{{not-json}}\n")])
    execution, client, _, _, _ = _execution(tmp_path, process=process)
    seen = []

    result = execute_daytona_job(
        execution,
        client_factory=lambda *_: client,
        progress_callback=seen.append,
        poll_wait=lambda: None,
    )

    assert result.result.job_id == "job-1"
    assert seen == []


def test_progress_logs_accept_only_complete_canonical_safe_monotonic_events(tmp_path):
    from backend.app.daytona import execute_daytona_job

    foreign = replace(EVENT_1, job_id="other-job")
    regressing = replace(EVENT_2, progress=34)
    secret = EVENT_2.to_mapping() | {"sequence": 3, "message": "Bearer secret"}
    later = replace(EVENT_2, sequence=4)
    stdout = "noise\n" + "".join(
        (
            LIVE_PROGRESS_PREFIX + canonical_json_bytes(foreign.to_mapping()).decode(),
            LIVE_PROGRESS_PREFIX + canonical_json_bytes(EVENT_1.to_mapping()).decode(),
            LIVE_PROGRESS_PREFIX + canonical_json_bytes(EVENT_1.to_mapping()).decode(),
            LIVE_PROGRESS_PREFIX + canonical_json_bytes(regressing.to_mapping()).decode(),
            LIVE_PROGRESS_PREFIX + canonical_json_bytes(secret).decode(),
            LIVE_PROGRESS_PREFIX + json.dumps(EVENT_2.to_mapping()) + "\n",
            LIVE_PROGRESS_PREFIX + canonical_json_bytes(later.to_mapping()).decode().rstrip("\n"),
        )
    )
    process = _Process(session_states=[(0, stdout)])
    execution, client, _, _, _ = _execution(tmp_path, process=process)
    seen = []

    execute_daytona_job(
        execution, client_factory=lambda *_: client, progress_callback=seen.append
    )

    assert seen == [EVENT_1]


def test_partial_progress_line_is_delivered_once_after_it_becomes_complete(tmp_path):
    from backend.app.daytona import execute_daytona_job

    complete = LIVE_PROGRESS_PREFIX + canonical_json_bytes(EVENT_1.to_mapping()).decode()
    process = _Process(
        session_states=[(None, complete.rstrip("\n")), (0, complete)]
    )
    execution, client, _, _, _ = _execution(tmp_path, process=process)
    seen = []

    execute_daytona_job(
        execution,
        client_factory=lambda *_: client,
        progress_callback=seen.append,
        poll_wait=lambda: None,
    )

    assert seen == [EVENT_1]


@pytest.mark.parametrize("limit", ["line", "total"])
def test_oversized_progress_telemetry_is_ignored(tmp_path, monkeypatch, limit):
    import backend.app.daytona as daytona

    payload = canonical_json_bytes(EVENT_1.to_mapping())
    stdout = LIVE_PROGRESS_PREFIX + payload.decode()
    if limit == "line":
        monkeypatch.setattr(daytona, "MAX_PROGRESS_LINE_BYTES", len(payload) - 1)
    else:
        monkeypatch.setattr(daytona, "MAX_PROGRESS_TOTAL_BYTES", len(stdout.encode()) - 1)
    process = _Process(session_states=[(0, stdout)])
    execution, client, _, _, _ = _execution(tmp_path, process=process)
    seen = []

    result = daytona.execute_daytona_job(
        execution, client_factory=lambda *_: client, progress_callback=seen.append
    )

    assert result.result.job_id == "job-1"
    assert seen == []


def test_log_and_callback_failures_are_telemetry_loss(tmp_path):
    from backend.app.daytona import execute_daytona_job

    stdout = (
        LIVE_PROGRESS_PREFIX
        + canonical_json_bytes(EVENT_1.to_mapping()).decode()
        + LIVE_PROGRESS_PREFIX
        + canonical_json_bytes(EVENT_2.to_mapping()).decode()
    )
    process = _Process(session_states=[(None, stdout), (0, stdout)])
    execution, client, _, _, _ = _execution(tmp_path, process=process)
    seen = []

    def callback(event):
        seen.append(event)
        if event == EVENT_1:
            raise RuntimeError("callback-secret")

    result = execute_daytona_job(
        execution,
        client_factory=lambda *_: client,
        progress_callback=callback,
        poll_wait=lambda: None,
    )
    assert result.result.job_id == "job-1"
    assert seen == [EVENT_1, EVENT_2]

    second = tmp_path / "second"
    second.mkdir()
    process = _Process(logs_error=TimeoutError("provider-secret"))
    execution, client, _, _, _ = _execution(second, process=process)
    result = execute_daytona_job(
        execution, client_factory=lambda *_: client, progress_callback=seen.append
    )
    assert result.result.job_id == "job-1"


def test_session_timeout_is_stable_and_attempts_both_cleanups(tmp_path, monkeypatch):
    import backend.app.daytona as daytona

    process = _Process(session_states=[(None, "")])
    execution, client, sandbox, _, _ = _execution(tmp_path, process=process)
    now = [0.0]
    monkeypatch.setattr(daytona.time, "monotonic", lambda: now[0])

    def poll_wait():
        now[0] = float(execution.policy.execution_timeout_seconds)

    with pytest.raises(daytona.DaytonaExecutionError) as raised:
        daytona.execute_daytona_job(
            execution, client_factory=lambda *_: client, poll_wait=poll_wait
        )

    assert str(raised.value) == "execute: worker timed out"
    assert len(process.status_calls) == 1
    assert process.deleted_sessions == ["fa-job-1"]
    assert client.delete_calls == [(sandbox, 120, True)]


@pytest.mark.parametrize("status_elapsed", [10, 8999])
def test_timely_session_success_survives_bounded_log_timeout(
    tmp_path, monkeypatch, status_elapsed
):
    import backend.app.daytona as daytona

    process = _Process()
    execution, client, _, _, _ = _execution(tmp_path, process=process)
    now = [0.0]
    monkeypatch.setattr(daytona.time, "monotonic", lambda: now[0])
    original_status = process.get_session_command
    log_timeouts = []

    def timely_status(*args, **kwargs):
        now[0] = status_elapsed
        return original_status(*args, **kwargs)

    def timeout_logs(*args, request_timeout, **kwargs):
        log_timeouts.append(request_timeout)
        now[0] += request_timeout
        raise TimeoutError("Bearer provider-secret")

    process.get_session_command = timely_status
    process.get_session_command_logs = timeout_logs

    outcome = daytona.execute_daytona_job(
        execution, client_factory=lambda *_: client, progress_callback=lambda _: None
    )

    assert outcome.result.job_id == "job-1"
    assert len(log_timeouts) == 1
    assert 0 < log_timeouts[0] <= 2
    if status_elapsed == 8999:
        assert now[0] > execution.policy.execution_timeout_seconds


@pytest.mark.parametrize("operation", ["create", "status", "logs", "delete"])
def test_session_requests_use_bounded_remaining_budget(tmp_path, monkeypatch, operation):
    import backend.app.daytona as daytona

    process = _Process()
    execution, client, _, _, _ = _execution(tmp_path, process=process)
    now = [0.0]
    monkeypatch.setattr(daytona.time, "monotonic", lambda: now[0])

    def spend(method, seconds):
        def call(*args, **kwargs):
            result = method(*args, **kwargs)
            now[0] += seconds
            return result
        return call

    process.execute_session_command = spend(process.execute_session_command, 7)
    process.get_session_command = spend(process.get_session_command, 11)
    process.get_session_command_logs = spend(process.get_session_command_logs, 13)

    outcome = daytona.execute_daytona_job(
        execution, client_factory=lambda *_: client, progress_callback=lambda _: None
    )

    assert outcome.result.job_id == "job-1"
    actual, expected = {
        "create": (process.created_sessions, [("fa-job-1", 600)]),
        "status": (process.status_calls, [("fa-job-1", "cmd-1", 8993)]),
        "logs": (process.log_calls, [("fa-job-1", "cmd-1", 2)]),
        "delete": (process.delete_timeouts, [120]),
    }[operation]
    assert actual == expected


@pytest.mark.parametrize("slow_call", [
    "execute_session_command", "get_session_command", "get_session_command_logs"
])
@pytest.mark.parametrize("elapsed", [9000, 9001])
def test_session_rejects_deadline_overrun_during_launch_status_or_running_logs(
    tmp_path, monkeypatch, slow_call, elapsed
):
    import backend.app.daytona as daytona

    process = _Process(session_states=[(None if slow_call == "get_session_command_logs" else 0, "")])
    execution, client, sandbox, _, _ = _execution(tmp_path, process=process)
    now = [0.0]
    monkeypatch.setattr(daytona.time, "monotonic", lambda: now[0])
    original = getattr(process, slow_call)

    def delayed(*args, **kwargs):
        result = original(*args, **kwargs)
        now[0] += elapsed
        return result

    setattr(process, slow_call, delayed)

    with pytest.raises(daytona.DaytonaExecutionError, match="^execute: worker timed out$"):
        daytona.execute_daytona_job(
            execution, client_factory=lambda *_: client, progress_callback=lambda _: None
        )

    assert process.deleted_sessions == ["fa-job-1"]
    assert process.delete_timeouts == [120]
    assert client.delete_calls == [(sandbox, 120, True)]
    assert sandbox.fs.downloads == []


def test_session_nonzero_is_stable_and_attempts_both_cleanups(tmp_path):
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job

    process = _Process(response=_Response(9, "Bearer provider-secret"))
    execution, client, sandbox, _, _ = _execution(tmp_path, process=process)

    with pytest.raises(DaytonaExecutionError) as raised:
        execute_daytona_job(execution, client_factory=lambda *_: client)

    assert str(raised.value) == "execute: worker returned nonzero"
    assert process.deleted_sessions == ["fa-job-1"]
    assert client.delete_calls == [(sandbox, 120, True)]


@pytest.mark.parametrize("failure", ["create", "start", "status", "delete"])
@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_session_lifecycle_failures_are_secret_safe_and_clean_sandbox(
    tmp_path, failure, cleanup_fails
):
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job

    error = TimeoutError("Bearer provider-secret")
    kwargs = {
        "create_error": error if failure == "create" else None,
        "error": error if failure == "start" else None,
        "status_error": error if failure == "status" else None,
        "delete_error": error if failure == "delete" else None,
    }
    process = _Process(**kwargs)
    execution, client, sandbox, _, _ = _execution(tmp_path, process=process)
    if cleanup_fails:
        client.delete_errors = [TimeoutError("provider-secret")] * 3

    with pytest.raises(DaytonaExecutionError) as raised:
        execute_daytona_job(execution, client_factory=lambda *_: client)

    if cleanup_fails:
        assert str(raised.value).startswith("cleanup: sandbox reference ")
        assert str(raised.value).endswith("destruction was not confirmed")
    else:
        assert str(raised.value) == "execute: provider operation failed"
    assert "provider-secret" not in str(raised.value)
    assert process.deleted_sessions == ([] if failure == "create" else ["fa-job-1"])
    assert client.delete_calls == [(sandbox, 120, True)] * (3 if cleanup_fails else 1)


def test_sdk_process_builds_the_pinned_async_request_and_forwards_session_calls():
    from backend.app.daytona import EXECUTION_COMMAND, SessionCommand, _SdkProcess

    class Request:
        def __init__(self, **values):
            self.values = values

    class Raw:
        def __init__(self):
            self.calls = []

        def create_session(self, *args, **kwargs):
            self.calls.append(("create", args, kwargs))

        def execute_session_command(self, *args, **kwargs):
            self.calls.append(("execute", args, kwargs))
            return "command"

        def get_session_command(self, *args, **kwargs):
            self.calls.append(("status", args, kwargs))
            return "status"

        def get_session_command_logs(self, *args, **kwargs):
            self.calls.append(("logs", args, kwargs))
            return "logs"

        def delete_session(self, *args, **kwargs):
            self.calls.append(("delete", args, kwargs))

    raw = Raw()
    process = _SdkProcess(raw, SimpleNamespace(SessionExecuteRequest=Request))

    process.create_session("session", 11)
    assert process.execute_session_command(
        "session", SessionCommand(EXECUTION_COMMAND, True), 12
    ) == "command"
    assert process.get_session_command("session", "command", 13) == "status"
    assert process.get_session_command_logs("session", "command", 14) == "logs"
    process.delete_session("session", 15)

    request = raw.calls[1][1][1]
    assert request.values == {"command": EXECUTION_COMMAND, "run_async": True}
    assert raw.calls == [
        ("create", ("session",), {"request_timeout": 11}),
        ("execute", ("session", request), {"timeout": 12}),
        ("status", ("session", "command"), {"request_timeout": 13}),
        ("logs", ("session", "command"), {"request_timeout": 14}),
        ("delete", ("session",), {"request_timeout": 15}),
    ]


def test_success_uses_exact_policy_stream_order_command_and_generation_downloads(tmp_path):
    from backend.app.daytona import EXECUTION_COMMAND, DaytonaSandboxSpec, execute_daytona_job

    execution, client, sandbox, factory_calls, expected = _execution(tmp_path)
    outcome = execute_daytona_job(execution, client_factory=lambda key, target: (factory_calls.append((key, target)) or client))

    assert factory_calls == [("daytona-secret-value", "us")]
    spec, timeout = client.create_calls[0]
    assert spec == DaytonaSandboxSpec(
        image=execution.policy.image, public=False, ephemeral=True, spot=False, ttl_minutes=180,
        network_block_all=True, env_vars=(), cpu=4, memory_gib=8, disk_gib=10, gpu=1,
        gpu_types=("RTX-PRO-6000", "H100"),
    )
    assert timeout == 600
    uploaded = [path for path, _, timeout in sandbox.fs.uploads]
    assert uploaded == [f"/home/daytona/job/{path}" for path in sorted([
        "evidence.json", "inputs/match.mp4", "job-request.json", "manifest.json", "models/model.bin", "sealed/receipt.json", "source/source.tar"
    ])]
    assert all(timeout == 1800 for _, _, timeout in sandbox.fs.uploads)
    assert sandbox.process.created_sessions == [("fa-job-1", 600)]
    assert sandbox.process.commands[0][0] == "fa-job-1"
    assert sandbox.process.commands[0][1].command == EXECUTION_COMMAND
    assert sandbox.process.commands[0][1].run_async is True
    assert sandbox.process.commands[0][2] == 9000
    assert sandbox.process.deleted_sessions == ["fa-job-1"]
    assert [path for path, _ in sandbox.fs.downloads] == [
        "/home/daytona/job/completion-receipt.json",
        f"/home/daytona/job/result-bundle.json.generations/{GENERATION}/result.json",
        f"/home/daytona/job/result-bundle.json.generations/{GENERATION}/result.processor-result.json",
        f"/home/daytona/job/result-bundle.json.generations/{GENERATION}/result.progress.jsonl",
    ]
    assert outcome.sandbox_id == "sb-123"
    assert (outcome.result, outcome.completion) == (expected[2], expected[3])
    assert outcome.processor_path.read_bytes() == b'{"detections":[]}'
    assert outcome.progress_path.read_bytes() == b""
    assert client.delete_calls == [(sandbox, 120, True)]


def test_adapter_accepts_the_real_workers_root_relative_result_paths(tmp_path, monkeypatch):
    from backend.app import gpu_worker
    from backend.app.daytona import DaytonaExecutionRequest, execute_daytona_job

    root, workspace, preflight, request, _, _, _, _ = _bundle(tmp_path)
    monkeypatch.setattr(gpu_worker, "_prepare_runtime", lambda *_: {})
    monkeypatch.setattr(
        gpu_worker,
        "process_video_input",
        lambda *_args, **_kwargs: {
            "rows": [
                {
                    "Frame_ID": 0,
                    "Timestamp": 0.0,
                    "Entity_Type": "ball",
                    "Track_ID": -1,
                    "X": 50.0,
                    "Y": 34.0,
                    "Conf": 0.9,
                }
            ],
            "trackColors": {},
        },
    )
    gpu_worker.run_worker(
        root / "job-request.json",
        root / "result-bundle.json",
        root / "completion-receipt.json",
    )
    remote = {
        f"/home/daytona/job/{path.relative_to(root).as_posix()}": path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
        and (
            path.name == "completion-receipt.json"
            or "result-bundle.json.generations" in path.parts
        )
    }
    sandbox = _Sandbox(remote)
    client = _Client(sandbox)
    outcome = execute_daytona_job(
        DaytonaExecutionRequest(
            "daytona-secret-value", load_daytona_policy(), root, workspace, preflight
        ),
        client_factory=lambda *_: client,
    )

    assert outcome.result.job_id == request.job_id
    assert outcome.completion.result_path == (
        PurePosixPath(outcome.result.result["processorResultPath"]).parent / "result.json"
    )
    processor_lines = outcome.processor_path.read_bytes().splitlines()
    assert json.loads(processor_lines[0]) == {
        "metadata": {"trackColors": {}}, "rowCount": 1, "schemaVersion": 1,
    }
    assert json.loads(processor_lines[1])["Frame_ID"] == 0


def test_upload_close_poison_prevents_result_transfer_and_preserves_staging(
    tmp_path, monkeypatch
):
    import backend.app.daytona as daytona

    execution, client, sandbox, _, _ = _execution(tmp_path)
    original_fdopen = daytona.os.fdopen
    original_preflight = daytona._preflight
    original_owner_init = daytona._StagingOwner.__init__
    original_fstat = daytona.os.fstat
    original_open = daytona.os.open
    wrappers = []
    poisoned = []
    post_poison_calls = []
    retain_uploads = []
    staging_owners = []

    class ClosePoisonHandle:
        def __init__(self, handle):
            self.handle = handle
            self.descriptor = handle.fileno()
            self.close_attempts = 0

        def read(self, size=-1):
            return self.handle.read(size)

        def seek(self, offset, whence=0):
            return self.handle.seek(offset, whence)

        def fileno(self):
            return self.descriptor

        def close(self):
            self.close_attempts += 1
            self.handle.close()
            if self is wrappers[0]:
                poisoned.append(self.descriptor)
                raise OSError(daytona.errno.EIO, "raw-close-secret")

    def controlled_fdopen(*args, **kwargs):
        if not retain_uploads:
            return original_fdopen(*args, **kwargs)
        wrapper = ClosePoisonHandle(original_fdopen(*args, **kwargs))
        wrappers.append(wrapper)
        return wrapper

    def complete_preflight(*args, **kwargs):
        result = original_preflight(*args, **kwargs)
        retain_uploads.append(True)
        return result

    def track_staging_owner(owner, *args, **kwargs):
        original_owner_init(owner, *args, **kwargs)
        staging_owners.append(owner)

    def track_fstat(descriptor):
        if poisoned and descriptor == poisoned[0]:
            post_poison_calls.append(("fstat", descriptor))
        return original_fstat(descriptor)

    def track_open(*args, **kwargs):
        descriptor = original_open(*args, **kwargs)
        if poisoned and descriptor == poisoned[0]:
            post_poison_calls.append(("open-result", descriptor))
        if poisoned and kwargs.get("dir_fd") == poisoned[0]:
            post_poison_calls.append(("open-parent", poisoned[0]))
        return descriptor

    monkeypatch.setattr(daytona.os, "fdopen", controlled_fdopen)
    monkeypatch.setattr(daytona, "_preflight", complete_preflight)
    monkeypatch.setattr(daytona._StagingOwner, "__init__", track_staging_owner)
    monkeypatch.setattr(daytona.os, "fstat", track_fstat)
    monkeypatch.setattr(daytona.os, "open", track_open)

    with pytest.raises(daytona._LocalStagingCleanupError) as raised:
        daytona.execute_daytona_job(execution, client_factory=lambda *_: client)

    assert str(raised.value) == "cleanup: local staging cleanup was not confirmed"
    assert "raw-close-secret" not in str(raised.value)
    assert client.delete_calls == [(sandbox, 120, True)]
    assert poisoned == [wrappers[0].descriptor]
    assert wrappers[0].close_attempts == 1
    assert post_poison_calls == []
    assert len(staging_owners) == 1
    assert staging_owners[0].closed
    for descriptor in staging_owners[0].descriptors:
        with pytest.raises(OSError) as closed:
            original_fstat(descriptor)
        assert closed.value.errno == daytona.errno.EBADF
    assert len(list(execution.workspace.glob("daytona-result-*"))) == 1
    assert list(execution.workspace.glob(".daytona-quarantine-*")) == []


@pytest.mark.parametrize("sandbox_cleanup_fails", [False, True])
def test_lifecycle_and_upload_close_failures_have_fixed_precedence(
    tmp_path, monkeypatch, sandbox_cleanup_fails
):
    import backend.app.daytona as daytona

    execution, client, sandbox, _, _ = _execution(
        tmp_path, response=_Response(9, "lifecycle-secret")
    )
    if sandbox_cleanup_fails:
        client.delete_errors = [RuntimeError("sandbox-secret")] * 3
    original_fdopen = daytona.os.fdopen
    original_preflight = daytona._preflight
    wrappers = []
    retain_uploads = []

    class ClosePoisonHandle:
        def __init__(self, handle):
            self.handle = handle
            self.descriptor = handle.fileno()
            self.close_attempts = 0

        def read(self, size=-1):
            return self.handle.read(size)

        def seek(self, offset, whence=0):
            return self.handle.seek(offset, whence)

        def fileno(self):
            return self.descriptor

        def close(self):
            self.close_attempts += 1
            self.handle.close()
            if self is wrappers[0]:
                raise OSError(daytona.errno.EIO, "raw-close-secret")

    def controlled_fdopen(*args, **kwargs):
        if not retain_uploads:
            return original_fdopen(*args, **kwargs)
        wrapper = ClosePoisonHandle(original_fdopen(*args, **kwargs))
        wrappers.append(wrapper)
        return wrapper

    def complete_preflight(*args, **kwargs):
        result = original_preflight(*args, **kwargs)
        retain_uploads.append(True)
        return result

    monkeypatch.setattr(daytona.os, "fdopen", controlled_fdopen)
    monkeypatch.setattr(daytona, "_preflight", complete_preflight)

    expected = (
        "cleanup: sandbox and local staging cleanup were not confirmed"
        if sandbox_cleanup_fails
        else "cleanup: lifecycle failed and local staging cleanup was not confirmed"
    )
    with pytest.raises(daytona.DaytonaExecutionError) as raised:
        daytona.execute_daytona_job(
            execution, client_factory=lambda *_: client, retry_wait=lambda: None
        )

    assert str(raised.value) == expected
    assert "raw-close-secret" not in str(raised.value)
    assert "lifecycle-secret" not in str(raised.value)
    assert "sandbox-secret" not in str(raised.value)
    assert wrappers[0].close_attempts == 1
    assert list(execution.workspace.glob("daytona-result-*")) == []
    assert len(client.delete_calls) == (3 if sandbox_cleanup_fails else 1)
    assert sandbox is client.sandbox


def test_upload_descriptors_close_once_before_successful_staging_release(
    tmp_path, monkeypatch
):
    import backend.app.daytona as daytona

    execution, client, _, _, _ = _execution(tmp_path)
    original_fdopen = daytona.os.fdopen
    original_preflight = daytona._preflight
    original_release = daytona._StagingOwner.release
    wrappers = []
    release_observations = []
    retain_uploads = []

    class CloseTrackingHandle:
        def __init__(self, handle):
            self.handle = handle
            self.descriptor = handle.fileno()
            self.close_attempts = 0

        def read(self, size=-1):
            return self.handle.read(size)

        def seek(self, offset, whence=0):
            return self.handle.seek(offset, whence)

        def fileno(self):
            return self.descriptor

        def close(self):
            self.close_attempts += 1
            self.handle.close()
            if self is wrappers[0]:
                raise OSError(daytona.errno.EBADF, "closed-secret")

    def controlled_fdopen(*args, **kwargs):
        if not retain_uploads:
            return original_fdopen(*args, **kwargs)
        wrapper = CloseTrackingHandle(original_fdopen(*args, **kwargs))
        wrappers.append(wrapper)
        return wrapper

    def complete_preflight(*args, **kwargs):
        result = original_preflight(*args, **kwargs)
        retain_uploads.append(True)
        return result

    def release_after_uploads(owner):
        release_observations.append([wrapper.close_attempts for wrapper in wrappers])
        return original_release(owner)

    monkeypatch.setattr(daytona.os, "fdopen", controlled_fdopen)
    monkeypatch.setattr(daytona, "_preflight", complete_preflight)
    monkeypatch.setattr(daytona._StagingOwner, "release", release_after_uploads)

    outcome = daytona.execute_daytona_job(execution, client_factory=lambda *_: client)

    assert outcome.sandbox_id == "sb-123"
    assert release_observations == [[1] * len(wrappers)]
    assert [wrapper.close_attempts for wrapper in wrappers] == [1] * len(wrappers)
    assert len(wrappers) > 1


def test_invalid_preflight_constructs_no_client(tmp_path):
    from backend.app.daytona import DaytonaExecutionError, DaytonaExecutionRequest, execute_daytona_job

    root, workspace, preflight, *_ = _bundle(tmp_path)
    invalid = PreflightResult("c" * 40, preflight.manifest_sha256, preflight.manifest_path, preflight.evidence_path, preflight.evidence_phase, preflight.evidence_sha256, preflight.artifacts, preflight.artifact_metadata)
    execution = DaytonaExecutionRequest("secret", load_daytona_policy(), root, workspace, invalid)
    called = []
    with pytest.raises(DaytonaExecutionError, match="preflight"):
        execute_daytona_job(execution, client_factory=lambda *_: called.append(True))
    assert called == []


@pytest.mark.parametrize("kind", ["create", "upload", "execute", "nonzero", "download"])
def test_every_post_create_failure_cleans_up(tmp_path, kind):
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job

    kwargs = {}
    if kind == "upload": kwargs["fail_upload"] = True
    if kind == "execute": kwargs["process_error"] = TimeoutError("Bearer very-secret")
    if kind == "nonzero": kwargs["response"] = _Response(9, "api_key=very-secret" + "x" * 10000)
    execution, client, sandbox, _, _ = _execution(tmp_path, **kwargs)
    if kind == "create": client.create_error = RuntimeError("create password=secret")
    if kind == "download": sandbox.fs.fail_download = "/home/daytona/job/completion-receipt.json"
    with pytest.raises(DaytonaExecutionError) as raised:
        execute_daytona_job(execution, client_factory=lambda *_: client)
    assert "very-secret" not in str(raised.value)
    assert "daytona-secret-value" not in str(raised.value)
    assert len(str(raised.value)) < 1000
    assert len(client.delete_calls) == (0 if kind == "create" else 1)


def test_unreturned_sdk_sandbox_is_recovered_by_outer_cleanup_without_secret_leak(tmp_path):
    import backend.app.daytona as daytona

    execution, client, sandbox, _, _ = _execution(
        tmp_path, sandbox_id="Bearer provider-secret"
    )
    client.create_error = daytona._UnreturnedSandboxCleanupError(sandbox)
    client.delete_errors = [RuntimeError("delete-secret")] * execution.policy.cleanup_attempts

    with pytest.raises(daytona.DaytonaExecutionError) as raised:
        daytona.execute_daytona_job(
            execution, client_factory=lambda *_: client, retry_wait=lambda: None
        )

    assert "cleanup: sandbox reference" in str(raised.value)
    assert "secret" not in str(raised.value)
    assert client.delete_calls == [
        (sandbox, execution.policy.delete_timeout_seconds, True)
    ] * execution.policy.cleanup_attempts


def test_cleanup_retries_and_confirmed_absence_is_success(tmp_path):
    from backend.app.daytona import DaytonaConfirmedAbsent, execute_daytona_job

    execution, client, sandbox, _, _ = _execution(tmp_path)
    client.delete_errors = [RuntimeError("one"), DaytonaConfirmedAbsent()]
    outcome = execute_daytona_job(execution, client_factory=lambda *_: client, retry_wait=lambda: None)
    assert outcome.sandbox_id == "sb-123"
    assert len(client.delete_calls) == 2


def test_cleanup_failure_overrides_valid_result(tmp_path):
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job

    execution, client, _, _, _ = _execution(tmp_path)
    client.delete_errors = [RuntimeError("fail")] * 3
    with pytest.raises(DaytonaExecutionError, match="cleanup") as raised:
        execute_daytona_job(execution, client_factory=lambda *_: client, retry_wait=lambda: None)
    assert "sb-123" not in str(raised.value)
    assert len(client.delete_calls) == 3


def test_cleanup_failure_removes_unreturned_staging_and_preserves_workspace_input(tmp_path):
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job

    execution, client, _, _, _ = _execution(tmp_path)
    protected = execution.workspace / "input" / "caller-owned.txt"
    protected.parent.mkdir()
    protected.write_bytes(b"caller-owned")
    client.delete_errors = [RuntimeError("fail")] * 3

    with pytest.raises(DaytonaExecutionError, match="cleanup"):
        execute_daytona_job(
            execution,
            client_factory=lambda *_: client,
            retry_wait=lambda: None,
        )

    assert protected.read_bytes() == b"caller-owned"
    assert list(execution.workspace.glob("daytona-result-*")) == []
    assert len(client.delete_calls) == 3


def test_staging_cleanup_workspace_substitution_never_deletes_replacement(tmp_path, monkeypatch):
    import backend.app.daytona as daytona

    execution, client, _, _, _ = _execution(tmp_path)
    client.delete_errors = [RuntimeError("fail")] * 3
    original_rename = daytona.os.rename
    original_move = daytona._rename_noreplace
    swapped = []

    def swap_then_move(src_dir_fd, source, dst_dir_fd, destination):
        if not swapped and str(source).startswith("daytona-result-"):
            staging = execution.workspace / str(source)
            moved = execution.workspace / "caller-preserved-original-staging"
            original_rename(staging, moved)
            staging.mkdir()
            (staging / "caller-owned.txt").write_bytes(b"caller-owned")
            swapped.append((staging, moved))
        return original_move(src_dir_fd, source, dst_dir_fd, destination)

    monkeypatch.setattr(daytona, "_rename_noreplace", swap_then_move)
    with pytest.raises(daytona.DaytonaExecutionError, match="local staging cleanup"):
        daytona.execute_daytona_job(
            execution, client_factory=lambda *_: client, retry_wait=lambda: None
        )

    replacement, retained = swapped[0]
    assert (replacement / "caller-owned.txt").read_bytes() == b"caller-owned"
    assert retained.is_dir()
    assert list(execution.workspace.glob(".daytona-quarantine-*")) == []


def test_recursive_staging_deletion_failure_is_not_silently_swallowed(tmp_path, monkeypatch):
    import backend.app.daytona as daytona

    execution, client, _, _, _ = _execution(tmp_path)
    client.delete_errors = [RuntimeError("provider-secret")] * 3
    monkeypatch.setattr(daytona.shutil, "rmtree", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("hunter2")))

    with pytest.raises(daytona.DaytonaExecutionError) as raised:
        daytona.execute_daytona_job(
            execution, client_factory=lambda *_: client, retry_wait=lambda: None
        )

    assert str(raised.value) == "cleanup: sandbox and local staging cleanup were not confirmed"
    assert "hunter2" not in str(raised.value)
    assert "provider-secret" not in str(raised.value)


def test_successful_staging_cleanup_confirms_absence_and_preserves_similar_paths(tmp_path):
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job

    execution, client, _, _, _ = _execution(tmp_path)
    similar = execution.workspace / "daytona-result-caller-owned"
    similar.mkdir()
    (similar / "input.txt").write_bytes(b"keep")
    client.delete_errors = [RuntimeError("fail")] * 3

    with pytest.raises(DaytonaExecutionError, match="cleanup: sandbox reference"):
        execute_daytona_job(
            execution, client_factory=lambda *_: client, retry_wait=lambda: None
        )

    assert (similar / "input.txt").read_bytes() == b"keep"
    assert [path for path in execution.workspace.glob("daytona-result-*") if path != similar] == []
    assert list(execution.workspace.glob(".daytona-quarantine-*")) == []


def test_staging_cleanup_creates_quarantine_relative_to_retained_workspace(tmp_path, monkeypatch):
    import backend.app.daytona as daytona

    execution, client, _, _, _ = _execution(tmp_path)
    client.delete_errors = [RuntimeError("fail")] * 3
    original_mkdtemp = daytona.tempfile.mkdtemp

    def result_staging_only(*args, **kwargs):
        if kwargs.get("prefix") == ".daytona-quarantine-":
            raise AssertionError("quarantine creation used the workspace pathname")
        return original_mkdtemp(*args, **kwargs)

    monkeypatch.setattr(daytona.tempfile, "mkdtemp", result_staging_only)

    with pytest.raises(daytona.DaytonaExecutionError, match="cleanup: sandbox reference"):
        daytona.execute_daytona_job(
            execution, client_factory=lambda *_: client, retry_wait=lambda: None
        )


def test_staging_cleanup_move_is_atomic_no_clobber(tmp_path, monkeypatch):
    import backend.app.daytona as daytona

    execution, client, _, _, _ = _execution(tmp_path)
    client.delete_errors = [RuntimeError("fail")] * 3
    original_mkdir = daytona.os.mkdir
    fixed_random = b"\0" * 16

    def collide_with_quarantine_entry(path, mode=0o777, *, dir_fd=None):
        original_mkdir(path, mode, dir_fd=dir_fd)
        if str(path).startswith(".daytona-quarantine-"):
            quarantine_fd = daytona.os.open(
                path,
                daytona.os.O_RDONLY | daytona.os.O_DIRECTORY | daytona.os.O_NOFOLLOW,
                dir_fd=dir_fd,
            )
            try:
                original_mkdir(
                    f"staging-{fixed_random.hex()}", 0o700, dir_fd=quarantine_fd
                )
            finally:
                daytona.os.close(quarantine_fd)

    monkeypatch.setattr(daytona.os, "urandom", lambda _: fixed_random)
    monkeypatch.setattr(daytona.os, "mkdir", collide_with_quarantine_entry)

    with pytest.raises(daytona.DaytonaExecutionError) as raised:
        daytona.execute_daytona_job(
            execution, client_factory=lambda *_: client, retry_wait=lambda: None
        )

    assert str(raised.value) == "cleanup: sandbox and local staging cleanup were not confirmed"
    assert len(list(execution.workspace.glob("daytona-result-*"))) == 1


def test_staging_owner_close_failure_attempts_every_descriptor_and_is_secret_safe(
    tmp_path, monkeypatch
):
    import backend.app.daytona as daytona

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    staging = workspace / "daytona-result-owned"
    staging.mkdir()
    owner = daytona._StagingOwner(workspace, staging)
    staging_fd = owner.staging_fd
    workspace_fd = owner.workspace_fd
    cleanup_staging_fd = owner.cleanup_staging_fd
    cleanup_workspace_fd = owner.cleanup_workspace_fd
    original_close = daytona.os.close
    closed = []

    def fail_staging_close(descriptor):
        closed.append(descriptor)
        if descriptor == staging_fd:
            raise OSError("descriptor-secret")
        original_close(descriptor)

    monkeypatch.setattr(daytona.os, "close", fail_staging_close)
    try:
        with pytest.raises(daytona.DaytonaExecutionError) as raised:
            owner.release()
        assert str(raised.value) == "cleanup: local staging cleanup was not confirmed"
        assert {staging_fd, workspace_fd, cleanup_staging_fd, cleanup_workspace_fd} <= set(closed)
        assert daytona.os.fstat(staging_fd)
        for descriptor in (workspace_fd, cleanup_staging_fd, cleanup_workspace_fd):
            with pytest.raises(OSError):
                daytona.os.fstat(descriptor)
        assert "descriptor-secret" not in str(raised.value)
    finally:
        for descriptor in (staging_fd, workspace_fd):
            try:
                original_close(descriptor)
            except OSError:
                pass


@pytest.mark.parametrize(
    "failed_attribute",
    ["staging_fd", "workspace_fd", "cleanup_staging_fd", "cleanup_workspace_fd"],
)
def test_staging_transfer_close_failure_deletes_unreturned_staging(
    tmp_path, monkeypatch, failed_attribute
):
    import backend.app.daytona as daytona

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    staging = workspace / "daytona-result-owned"
    staging.mkdir()
    (staging / "result.json").write_bytes(b"validated")
    owner = daytona._StagingOwner(workspace, staging)
    failed_fd = getattr(owner, failed_attribute)
    original_close = daytona.os.close
    failures = []

    def fail_once_before_close(descriptor):
        if descriptor == failed_fd and not failures:
            failures.append(descriptor)
            raise OSError("descriptor-secret")
        original_close(descriptor)

    monkeypatch.setattr(daytona.os, "close", fail_once_before_close)
    try:
        with pytest.raises(daytona.DaytonaExecutionError) as raised:
            owner.release()

        assert str(raised.value) == "cleanup: local staging cleanup was not confirmed"
        assert failures == [failed_fd]
        assert staging.is_dir()
        assert list(workspace.glob(".daytona-quarantine-*")) == []
        assert daytona.os.fstat(failed_fd)
        assert failed_attribute in owner._uncertain_descriptors
    finally:
        original_close(failed_fd)


@pytest.mark.parametrize("failed_attribute", ["staging_fd", "workspace_fd"])
def test_staging_transfer_does_not_double_close_released_descriptor(
    tmp_path, monkeypatch, failed_attribute
):
    import backend.app.daytona as daytona

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    staging = workspace / "daytona-result-owned"
    staging.mkdir()
    owner = daytona._StagingOwner(workspace, staging)
    failed_fd = getattr(owner, failed_attribute)
    original_close = daytona.os.close
    attempts = []

    def close_then_fail_once(descriptor):
        if descriptor == failed_fd and not attempts:
            attempts.append(descriptor)
            original_close(descriptor)
            raise OSError("descriptor-secret")
        original_close(descriptor)

    monkeypatch.setattr(daytona.os, "close", close_then_fail_once)

    with pytest.raises(daytona.DaytonaExecutionError) as raised:
        owner.release()

    assert str(raised.value) == "cleanup: local staging cleanup was not confirmed"
    assert attempts == [failed_fd]
    assert staging.is_dir()
    assert "descriptor-secret" not in str(raised.value)


@pytest.mark.parametrize("failed_attribute", ["staging_fd", "workspace_fd"])
def test_staging_transfer_clears_close_confirmed_ebadf(
    tmp_path, monkeypatch, failed_attribute
):
    import backend.app.daytona as daytona

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    staging = workspace / "daytona-result-owned"
    staging.mkdir()
    owner = daytona._StagingOwner(workspace, staging)
    failed_fd = getattr(owner, failed_attribute)
    original_close = daytona.os.close
    failed = []

    def close_then_report_ebadf(descriptor):
        if descriptor == failed_fd and not failed:
            failed.append(descriptor)
            original_close(descriptor)
            raise OSError(daytona.errno.EBADF, "descriptor-secret")
        original_close(descriptor)

    monkeypatch.setattr(daytona.os, "close", close_then_report_ebadf)

    owner.release()

    assert failed == [failed_fd]
    assert staging.is_dir()
    assert owner.closed


def test_staging_transfer_never_closes_same_inode_reused_fd_number(
    tmp_path, monkeypatch
):
    import backend.app.daytona as daytona

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    staging = workspace / "daytona-result-owned"
    staging.mkdir()
    owner = daytona._StagingOwner(workspace, staging)
    failed_fd = owner.staging_fd
    original_open = daytona.os.open
    original_close = daytona.os.close
    original_fstat = daytona.os.fstat
    original_stat = daytona.os.stat
    original_mkdir = daytona.os.mkdir
    original_rename = daytona.os.rename
    original_rmdir = daytona.os.rmdir
    original_unlink = daytona.os.unlink
    original_dup = daytona.os.dup
    attempts = []
    caller_fds = []
    poisoned = []
    post_error_calls = []

    def close_reopen_same_inode_then_fail(descriptor):
        if descriptor == failed_fd:
            attempts.append(descriptor)
            if len(attempts) == 1:
                original_close(descriptor)
                caller_fd = original_open(
                    staging,
                    daytona.os.O_RDONLY
                    | daytona.os.O_DIRECTORY
                    | daytona.os.O_NOFOLLOW,
                )
                assert caller_fd == failed_fd
                caller_fds.append(caller_fd)
                poisoned.append(failed_fd)
                raise OSError(daytona.errno.EIO, "close-secret")
            if poisoned:
                post_error_calls.append(("close", descriptor))
        original_close(descriptor)

    def track_fstat(descriptor):
        if poisoned and descriptor == failed_fd:
            post_error_calls.append(("fstat", descriptor))
        return original_fstat(descriptor)

    def track_stat(path, *args, **kwargs):
        if poisoned and (path == failed_fd or kwargs.get("dir_fd") == failed_fd):
            post_error_calls.append(("stat", failed_fd))
        return original_stat(path, *args, **kwargs)

    def track_open(path, flags, mode=0o777, *, dir_fd=None):
        if poisoned and dir_fd == failed_fd:
            post_error_calls.append(("open", failed_fd))
        return original_open(path, flags, mode, dir_fd=dir_fd)

    def track_mkdir(path, mode=0o777, *, dir_fd=None):
        if poisoned and dir_fd == failed_fd:
            post_error_calls.append(("mkdir", failed_fd))
        return original_mkdir(path, mode, dir_fd=dir_fd)

    def track_rename(source, destination, *, src_dir_fd=None, dst_dir_fd=None):
        if poisoned and failed_fd in {src_dir_fd, dst_dir_fd}:
            post_error_calls.append(("rename", failed_fd))
        return original_rename(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    def track_rmdir(path, *, dir_fd=None):
        if poisoned and dir_fd == failed_fd:
            post_error_calls.append(("rmdir", failed_fd))
        return original_rmdir(path, dir_fd=dir_fd)

    def track_unlink(path, *, dir_fd=None):
        if poisoned and dir_fd == failed_fd:
            post_error_calls.append(("unlink", failed_fd))
        return original_unlink(path, dir_fd=dir_fd)

    def track_dup(descriptor):
        if poisoned and descriptor == failed_fd:
            post_error_calls.append(("dup", descriptor))
        return original_dup(descriptor)

    monkeypatch.setattr(daytona.os, "close", close_reopen_same_inode_then_fail)
    monkeypatch.setattr(daytona.os, "fstat", track_fstat)
    monkeypatch.setattr(daytona.os, "stat", track_stat)
    monkeypatch.setattr(daytona.os, "open", track_open)
    monkeypatch.setattr(daytona.os, "mkdir", track_mkdir)
    monkeypatch.setattr(daytona.os, "rename", track_rename)
    monkeypatch.setattr(daytona.os, "rmdir", track_rmdir)
    monkeypatch.setattr(daytona.os, "unlink", track_unlink)
    monkeypatch.setattr(daytona.os, "dup", track_dup)
    try:
        with pytest.raises(daytona.DaytonaExecutionError) as raised:
            owner.release()
        assert str(raised.value) == "cleanup: local staging cleanup was not confirmed"
        assert attempts == [failed_fd]
        assert post_error_calls == []
        assert original_fstat(caller_fds[0])
        assert staging.is_dir()
        assert list(workspace.glob(".daytona-quarantine-*")) == []
        assert "close-secret" not in str(raised.value)
    finally:
        for descriptor in caller_fds:
            try:
                original_close(descriptor)
            except OSError:
                pass


def test_staging_transfer_poison_halts_before_future_fd_reuse(tmp_path, monkeypatch):
    import backend.app.daytona as daytona

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    caller_path = workspace / "caller-owned.txt"
    caller_path.write_bytes(b"keep")
    staging = workspace / "daytona-result-owned"
    staging.mkdir()
    owner = daytona._StagingOwner(workspace, staging)
    failed_fd = owner.staging_fd
    original_open = daytona.os.open
    original_close = daytona.os.close
    original_fstat = daytona.os.fstat
    original_stat = daytona.os.stat
    original_rmtree = daytona.shutil.rmtree
    poisoned = []
    post_error_calls = []

    def close_then_poison(descriptor):
        if descriptor == failed_fd and not poisoned:
            original_close(descriptor)
            poisoned.append(descriptor)
            raise OSError(daytona.errno.EIO, "close-secret")
        if poisoned and descriptor == failed_fd:
            post_error_calls.append(("close", descriptor))
        original_close(descriptor)

    def track_open(path, flags, mode=0o777, *, dir_fd=None):
        descriptor = original_open(path, flags, mode, dir_fd=dir_fd)
        if poisoned and descriptor == failed_fd:
            post_error_calls.append(("open-result", descriptor))
        if poisoned and dir_fd == failed_fd:
            post_error_calls.append(("open-parent", failed_fd))
        return descriptor

    def track_fstat(descriptor):
        if poisoned and descriptor == failed_fd:
            post_error_calls.append(("fstat", descriptor))
        return original_fstat(descriptor)

    def track_stat(path, *args, **kwargs):
        if poisoned and (path == failed_fd or kwargs.get("dir_fd") == failed_fd):
            post_error_calls.append(("stat", failed_fd))
        return original_stat(path, *args, **kwargs)

    def track_rmtree(path, *args, **kwargs):
        if poisoned and kwargs.get("dir_fd") == failed_fd:
            post_error_calls.append(("rmtree", failed_fd))
        return original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(daytona.os, "close", close_then_poison)
    monkeypatch.setattr(daytona.os, "open", track_open)
    monkeypatch.setattr(daytona.os, "fstat", track_fstat)
    monkeypatch.setattr(daytona.os, "stat", track_stat)
    monkeypatch.setattr(daytona.shutil, "rmtree", track_rmtree)

    with pytest.raises(daytona.DaytonaExecutionError) as raised:
        owner.release()

    assert str(raised.value) == "cleanup: local staging cleanup was not confirmed"
    assert post_error_calls == []
    assert staging.is_dir()
    assert caller_path.read_bytes() == b"keep"
    assert list(workspace.glob(".daytona-quarantine-*")) == []
    assert owner._poisoned_descriptors == {failed_fd}
    assert "close-secret" not in str(raised.value)


def test_staging_transfer_non_ebadf_probe_preserves_uncertain_descriptor(
    tmp_path, monkeypatch
):
    import backend.app.daytona as daytona

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    staging = workspace / "daytona-result-owned"
    staging.mkdir()
    owner = daytona._StagingOwner(workspace, staging)
    failed_fd = owner.staging_fd
    original_close = daytona.os.close
    original_fstat = daytona.os.fstat
    close_failed = []

    def fail_close_once(descriptor):
        if descriptor == failed_fd and not close_failed:
            close_failed.append(descriptor)
            raise OSError("close-secret")
        original_close(descriptor)

    def fail_reconciliation(descriptor):
        if descriptor == failed_fd and close_failed:
            raise OSError("validation-secret")
        return original_fstat(descriptor)

    monkeypatch.setattr(daytona.os, "close", fail_close_once)
    monkeypatch.setattr(daytona.os, "fstat", fail_reconciliation)
    try:
        with pytest.raises(daytona.DaytonaExecutionError) as raised:
            owner.release()
        assert str(raised.value) == "cleanup: local staging cleanup was not confirmed"
        assert original_fstat(failed_fd)
        assert owner.staging_fd == failed_fd
        assert "staging_fd" in owner._uncertain_descriptors
        assert staging.is_dir()
        assert "close-secret" not in str(raised.value)
        assert "validation-secret" not in str(raised.value)
    finally:
        original_close(failed_fd)


def test_staging_transfer_eio_probe_preserves_exact_uncertain_fd(
    tmp_path, monkeypatch
):
    import backend.app.daytona as daytona

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    caller_path = workspace / "caller-owned.txt"
    caller_path.write_bytes(b"keep")
    staging = workspace / "daytona-result-owned"
    staging.mkdir()
    owner = daytona._StagingOwner(workspace, staging)
    failed_fd = owner.cleanup_workspace_fd
    original_close = daytona.os.close
    original_fstat = daytona.os.fstat
    close_failed = []

    def fail_close_once(descriptor):
        if descriptor == failed_fd and not close_failed:
            close_failed.append(descriptor)
            raise OSError("close-secret")
        original_close(descriptor)

    def fail_primary_probe(descriptor):
        if descriptor == failed_fd and close_failed:
            raise OSError(daytona.errno.EIO, "validation-secret")
        return original_fstat(descriptor)

    monkeypatch.setattr(daytona.os, "close", fail_close_once)
    monkeypatch.setattr(daytona.os, "fstat", fail_primary_probe)
    try:
        with pytest.raises(daytona.DaytonaExecutionError) as raised:
            owner.release()
        assert str(raised.value) == "cleanup: local staging cleanup was not confirmed"
        assert staging.is_dir()
        assert caller_path.read_bytes() == b"keep"
        assert original_fstat(failed_fd)
        assert owner.cleanup_workspace_fd == failed_fd
        assert "cleanup_workspace_fd" in owner._uncertain_descriptors
        assert "close-secret" not in str(raised.value)
        assert "validation-secret" not in str(raised.value)
    finally:
        original_close(failed_fd)


def test_staging_transfer_persistent_eio_preserves_uncertain_fd_ownership(
    tmp_path, monkeypatch
):
    import backend.app.daytona as daytona

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    staging = workspace / "daytona-result-owned"
    staging.mkdir()
    owner = daytona._StagingOwner(workspace, staging)
    failed_fd = owner.cleanup_workspace_fd
    original_close = daytona.os.close
    original_fstat = daytona.os.fstat
    original_stat = daytona.os.stat
    close_failed = []

    def fail_close_once(descriptor):
        if descriptor == failed_fd and not close_failed:
            close_failed.append(descriptor)
            raise OSError("close-secret")
        original_close(descriptor)

    def fail_primary_probe(descriptor):
        if descriptor == failed_fd and close_failed:
            raise OSError(daytona.errno.EIO, "primary-secret")
        return original_fstat(descriptor)

    def fail_secondary_probe(path, *args, **kwargs):
        if path == failed_fd and close_failed:
            raise OSError(daytona.errno.EIO, "secondary-secret")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(daytona.os, "close", fail_close_once)
    monkeypatch.setattr(daytona.os, "fstat", fail_primary_probe)
    monkeypatch.setattr(daytona.os, "stat", fail_secondary_probe)
    try:
        with pytest.raises(daytona.DaytonaExecutionError) as raised:
            owner.release()
        assert str(raised.value) == "cleanup: local staging cleanup was not confirmed"
        assert staging.is_dir()
        assert owner.cleanup_workspace_fd == failed_fd
        assert "cleanup_workspace_fd" in owner._uncertain_descriptors
        assert original_fstat(failed_fd)
        assert "primary-secret" not in str(raised.value)
        assert "secondary-secret" not in str(raised.value)
    finally:
        original_close(failed_fd)


def test_staging_transfer_final_uncertain_descriptor_is_never_used_for_parent(
    tmp_path, monkeypatch
):
    import backend.app.daytona as daytona

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    staging = workspace / "daytona-result-owned"
    staging.mkdir()
    owner = daytona._StagingOwner(workspace, staging)
    failed_fd = owner.cleanup_staging_fd
    original_open = daytona.os.open
    original_close = daytona.os.close
    original_fstat = daytona.os.fstat
    failed = []
    derived = []

    def fail_cleanup_staging_once(descriptor):
        if descriptor == failed_fd and not failed:
            failed.append(descriptor)
            raise OSError("close-secret")
        original_close(descriptor)

    def track_derived_open(path, *args, **kwargs):
        descriptor = original_open(path, *args, **kwargs)
        if path == "..":
            derived.append(descriptor)
        return descriptor

    def fail_derived_fstat(descriptor):
        if descriptor in derived:
            raise OSError("validation-secret")
        return original_fstat(descriptor)

    monkeypatch.setattr(daytona.os, "close", fail_cleanup_staging_once)
    monkeypatch.setattr(daytona.os, "open", track_derived_open)
    monkeypatch.setattr(daytona.os, "fstat", fail_derived_fstat)

    try:
        with pytest.raises(daytona.DaytonaExecutionError) as raised:
            owner.release()

        assert str(raised.value) == "cleanup: local staging cleanup was not confirmed"
        assert derived == []
        assert staging.exists()
        assert original_fstat(failed_fd)
        assert owner.cleanup_staging_fd == failed_fd
        assert "cleanup_staging_fd" in owner._uncertain_descriptors
        assert "close-secret" not in str(raised.value)
        assert "validation-secret" not in str(raised.value)
    finally:
        original_close(failed_fd)


def test_staging_owner_construction_failure_closes_both_descriptors(tmp_path, monkeypatch):
    import backend.app.daytona as daytona

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    staging = workspace / "daytona-result-owned"
    staging.mkdir()
    original_open = daytona.os.open
    original_close = daytona.os.close
    original_fstat = daytona.os.fstat
    opened = []
    closed = []

    def track_open(*args, **kwargs):
        descriptor = original_open(*args, **kwargs)
        opened.append(descriptor)
        return descriptor

    def fail_staging_fstat(descriptor):
        if len(opened) >= 2 and descriptor == opened[-1]:
            raise OSError("descriptor-secret")
        return original_fstat(descriptor)

    def track_close(descriptor):
        closed.append(descriptor)
        original_close(descriptor)

    monkeypatch.setattr(daytona.os, "open", track_open)
    monkeypatch.setattr(daytona.os, "fstat", fail_staging_fstat)
    monkeypatch.setattr(daytona.os, "close", track_close)

    with pytest.raises(daytona.DaytonaExecutionError) as raised:
        daytona._StagingOwner(workspace, staging)

    assert str(raised.value) == "cleanup: local staging cleanup was not confirmed"
    assert closed == list(reversed(opened))
    assert "descriptor-secret" not in str(raised.value)


def test_private_quarantine_validation_failure_closes_descriptor(tmp_path, monkeypatch):
    import backend.app.daytona as daytona

    parent_fd = daytona.os.open(
        tmp_path, daytona.os.O_RDONLY | daytona.os.O_DIRECTORY | daytona.os.O_NOFOLLOW
    )
    original_close = daytona.os.close
    closed = []

    monkeypatch.setattr(
        daytona.os,
        "fstat",
        lambda _: (_ for _ in ()).throw(OSError("descriptor-secret")),
    )

    def track_close(descriptor):
        closed.append(descriptor)
        original_close(descriptor)

    monkeypatch.setattr(daytona.os, "close", track_close)
    try:
        with pytest.raises(daytona.DaytonaExecutionError) as raised:
            daytona._create_private_directory(parent_fd, ".daytona-quarantine-")
        assert str(raised.value) == "cleanup: local staging cleanup was not confirmed"
        assert len(closed) == 1
        assert "descriptor-secret" not in str(raised.value)
    finally:
        original_close(parent_fd)


def test_quarantine_close_failure_is_not_retried(tmp_path, monkeypatch):
    import backend.app.daytona as daytona

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    staging = workspace / "daytona-result-owned"
    staging.mkdir()
    owner = daytona._StagingOwner(workspace, staging)
    original_open = daytona.os.open
    original_close = daytona.os.close
    quarantine_fds = []
    close_attempts = []

    def track_open(path, *args, **kwargs):
        descriptor = original_open(path, *args, **kwargs)
        if str(path).startswith(".daytona-quarantine-"):
            quarantine_fds.append(descriptor)
        return descriptor

    def fail_after_quarantine_close(descriptor):
        if descriptor in quarantine_fds:
            close_attempts.append(descriptor)
            original_close(descriptor)
            raise OSError("descriptor-secret")
        original_close(descriptor)

    monkeypatch.setattr(daytona.os, "open", track_open)
    monkeypatch.setattr(daytona.os, "close", fail_after_quarantine_close)

    with pytest.raises(daytona._LocalStagingCleanupError) as raised:
        owner.cleanup()

    assert str(raised.value) == "cleanup: local staging cleanup was not confirmed"
    assert len(quarantine_fds) == 1
    assert close_attempts == quarantine_fds
    assert owner._poisoned_descriptors == set(quarantine_fds)
    assert "descriptor-secret" not in str(raised.value)


def test_moved_descriptor_close_poison_halts_before_recursive_cleanup(
    tmp_path, monkeypatch
):
    import backend.app.daytona as daytona

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    staging = workspace / "daytona-result-owned"
    staging.mkdir()
    (staging / "result.json").write_bytes(b"validated")
    owner = daytona._StagingOwner(workspace, staging)
    original_open = daytona.os.open
    original_close = daytona.os.close
    original_rmtree = daytona.shutil.rmtree
    quarantine_fds = []
    moved_fds = []
    poisoned = []
    post_poison_cleanup = []

    def track_open(path, *args, **kwargs):
        descriptor = original_open(path, *args, **kwargs)
        if str(path).startswith(".daytona-quarantine-"):
            quarantine_fds.append(descriptor)
        elif path.startswith("staging-"):
            moved_fds.append(descriptor)
        if poisoned:
            post_poison_cleanup.append(("open", descriptor))
        return descriptor

    def close_moved_then_poison(descriptor):
        if descriptor in moved_fds and not poisoned:
            original_close(descriptor)
            poisoned.append(descriptor)
            raise OSError(daytona.errno.EIO, "descriptor-secret")
        original_close(descriptor)

    def track_rmtree(*args, **kwargs):
        if poisoned:
            post_poison_cleanup.append(("rmtree", args[0]))
        return original_rmtree(*args, **kwargs)

    monkeypatch.setattr(daytona.os, "open", track_open)
    monkeypatch.setattr(daytona.os, "close", close_moved_then_poison)
    monkeypatch.setattr(daytona.shutil, "rmtree", track_rmtree)

    with pytest.raises(daytona._LocalStagingCleanupError) as raised:
        owner.cleanup()

    assert str(raised.value) == "cleanup: local staging cleanup was not confirmed"
    assert len(quarantine_fds) == 1
    assert len(moved_fds) == 1
    assert owner._poisoned_descriptors == set(moved_fds)
    assert post_poison_cleanup == []
    assert list(workspace.glob(".daytona-quarantine-*"))
    assert "descriptor-secret" not in str(raised.value)


def test_failed_lifecycle_plus_failed_staging_cleanup_has_fixed_precedence(tmp_path, monkeypatch):
    import backend.app.daytona as daytona

    execution, client, sandbox, _, _ = _execution(tmp_path)
    sandbox.fs.remote["/home/daytona/job/completion-receipt.json"] = b"not-json"
    monkeypatch.setattr(daytona.shutil, "rmtree", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("secret")))

    with pytest.raises(daytona.DaytonaExecutionError) as raised:
        daytona.execute_daytona_job(execution, client_factory=lambda *_: client)

    assert str(raised.value) == "cleanup: lifecycle failed and local staging cleanup was not confirmed"
    assert "secret" not in str(raised.value)


def test_lifecycle_local_and_sandbox_cleanup_failures_have_combined_precedence(
    tmp_path, monkeypatch
):
    import backend.app.daytona as daytona

    execution, client, sandbox, _, _ = _execution(tmp_path)
    sandbox.fs.remote["/home/daytona/job/completion-receipt.json"] = b"not-json"
    client.delete_errors = [RuntimeError("provider-secret")] * 3
    monkeypatch.setattr(
        daytona.shutil,
        "rmtree",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("local-secret")),
    )

    with pytest.raises(daytona.DaytonaExecutionError) as raised:
        daytona.execute_daytona_job(
            execution, client_factory=lambda *_: client, retry_wait=lambda: None
        )

    assert str(raised.value) == "cleanup: sandbox and local staging cleanup were not confirmed"
    assert "provider-secret" not in str(raised.value)
    assert "local-secret" not in str(raised.value)


def test_lifecycle_failure_with_local_cleanup_success_and_sandbox_failure_reports_sandbox(
    tmp_path,
):
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job

    execution, client, sandbox, _, _ = _execution(tmp_path)
    sandbox.fs.remote["/home/daytona/job/completion-receipt.json"] = b"not-json"
    client.delete_errors = [RuntimeError("provider-secret")] * 3

    with pytest.raises(DaytonaExecutionError) as raised:
        execute_daytona_job(
            execution, client_factory=lambda *_: client, retry_wait=lambda: None
        )

    assert "sandbox reference" in str(raised.value)
    assert "local staging" not in str(raised.value)
    assert "provider-secret" not in str(raised.value)


@pytest.mark.parametrize("mutation", [
    lambda remote: remote.__setitem__("/home/daytona/job/completion-receipt.json", b"not-json"),
    lambda remote: remote.__setitem__("/home/daytona/job/completion-receipt.json", b"x" * (4 * 1024 * 1024 + 1)),
    lambda remote: remote.__setitem__(f"/home/daytona/job/result-bundle.json.generations/{GENERATION}/result.json", b"{}\n"),
    lambda remote: remote.pop(f"/home/daytona/job/result-bundle.json.generations/{GENERATION}/result.processor-result.json"),
])
def test_corrupt_missing_or_oversized_download_fails_closed_and_cleans(tmp_path, mutation):
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job

    execution, client, sandbox, _, _ = _execution(tmp_path, remote_mutator=mutation)
    with pytest.raises(DaytonaExecutionError, match="download"):
        execute_daytona_job(execution, client_factory=lambda *_: client)
    assert len(client.delete_calls) == 1


@pytest.mark.parametrize("api_key", ["", "   ", "bad\0key"])
def test_invalid_api_key_causes_zero_client_construction(tmp_path, api_key):
    from dataclasses import replace
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job

    execution, _, _, _, _ = _execution(tmp_path)
    called = []
    with pytest.raises(DaytonaExecutionError, match="preflight"):
        execute_daytona_job(replace(execution, api_key=api_key), client_factory=lambda *_: called.append(True))
    assert called == []


def test_invalid_sandbox_identity_is_create_adjacent_failure_and_is_cleaned(tmp_path):
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job

    execution, client, sandbox, _, _ = _execution(tmp_path, sandbox_id="Bearer secret")
    with pytest.raises(DaytonaExecutionError, match="create"):
        execute_daytona_job(execution, client_factory=lambda *_: client)
    assert client.delete_calls == [(sandbox, 120, True)]


def test_cross_generation_result_is_rejected_after_completion_first_and_cleaned(tmp_path):
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job

    def mutate(remote):
        result_path = f"/home/daytona/job/result-bundle.json.generations/{GENERATION}/result.json"
        value = __import__("json").loads(remote[result_path])
        value["result"]["progressPath"] = "result-bundle.json.generations/ffffffffffffffffffffffffffffffff/result.progress.jsonl"
        remote[result_path] = canonical_json_bytes(value)

    execution, client, _, _, _ = _execution(tmp_path, remote_mutator=mutate)
    with pytest.raises(DaytonaExecutionError, match="download"):
        execute_daytona_job(execution, client_factory=lambda *_: client)
    assert len(client.delete_calls) == 1


def test_success_files_are_private_and_diagnostics_do_not_expose_signed_url(tmp_path):
    from backend.app.daytona import execute_daytona_job

    execution, client, sandbox, _, _ = _execution(tmp_path)
    sandbox.process.response.result = "/root/private/artifact https://host/x?X-Amz-Signature=secret"
    outcome = execute_daytona_job(execution, client_factory=lambda *_: client)
    rendered = repr(outcome.diagnostics)
    assert "/root/private" not in rendered
    assert "Signature" not in rendered
    assert "Bearer" not in rendered
    assert outcome.staging_root.stat().st_mode & 0o777 == 0o700
    assert outcome.processor_path.stat().st_mode & 0o777 == 0o600


def test_sdk_adapter_translates_policy_to_exact_pinned_sdk_objects(monkeypatch):
    from backend.app.daytona import DaytonaSandboxSpec, _SdkClient
    import backend.app.daytona as adapter

    def deterministic_urandom(size):
        assert size == 16
        return b"\xab" * size

    monkeypatch.setattr(adapter.os, "urandom", deterministic_urandom)

    class Resources:
        def __init__(self, *, cpu, memory, disk, gpu, gpu_type):
            self.values = {
                "cpu": cpu, "memory": memory, "disk": disk,
                "gpu": gpu, "gpu_type": gpu_type,
            }
    class CreateSandboxFromImageParams:
        def __init__(
            self, *, name, labels, image, public, ephemeral, spot, ttl_minutes,
            network_block_all, env_vars, resources
        ):
            self.values = {
                "name": name, "labels": labels,
                "image": image, "public": public, "ephemeral": ephemeral,
                "spot": spot, "ttl_minutes": ttl_minutes,
                "network_block_all": network_block_all, "env_vars": env_vars,
                "resources": resources,
            }
    class GpuType:
        RTX_PRO_6000 = "rtx"
        H100 = "h100"
    SDK = type("SDK", (), {
        "Resources": Resources,
        "CreateSandboxFromImageParams": CreateSandboxFromImageParams,
        "GpuType": GpuType, "DaytonaNotFoundError": LookupError,
    })
    class Raw:
        def __init__(self): self.calls = []
        def create(self, params, *, timeout):
            self.calls.append((params, timeout))
            return object()
    raw = Raw()
    spec = DaytonaSandboxSpec("image@sha256:digest", False, True, False, 45, True, (), 4, 8, 10, 1, ("RTX-PRO-6000", "H100"))
    _SdkClient(raw, SDK).create(spec, 600)
    params, timeout = raw.calls[0]
    assert timeout == 600
    assert params.values == {
        "name": f"fa-{'ab' * 16}",
        "labels": {"football-analyst-owner": "ab" * 16},
        "image": "image@sha256:digest", "public": False, "ephemeral": True,
        "spot": False, "ttl_minutes": 45, "network_block_all": True, "env_vars": {},
        "resources": params.values["resources"],
    }
    assert params.values["resources"].values == {
        "cpu": 4, "memory": 8, "disk": 10, "gpu": 1, "gpu_type": ["rtx", "h100"]
    }


def test_preflight_live_manifest_and_evidence_bind_by_identity_not_staging_path(tmp_path):
    from dataclasses import replace
    from backend.app.daytona import execute_daytona_job

    execution, client, _, _, _ = _execution(tmp_path)
    live = tmp_path / "live-release"
    live.mkdir()
    live_manifest = live / "v7.3.json"
    live_evidence = live / "verification.json"
    live_manifest.write_bytes(execution.preflight.manifest_path.read_bytes())
    live_evidence.write_bytes(execution.preflight.evidence_path.read_bytes())
    proof = replace(execution.preflight, manifest_path=live_manifest, evidence_path=live_evidence)

    outcome = execute_daytona_job(replace(execution, preflight=proof), client_factory=lambda *_: client)

    assert outcome.sandbox_id == "sb-123"


def test_noncanonical_request_and_forged_artifact_proof_each_build_no_client(tmp_path):
    from dataclasses import replace
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job

    execution, _, _, _, _ = _execution(tmp_path)
    called = []
    request_file = execution.bundle_root / "job-request.json"
    request_file.write_bytes(request_file.read_bytes().rstrip(b"\n") + b" \n")
    with pytest.raises(DaytonaExecutionError, match="preflight"):
        execute_daytona_job(execution, client_factory=lambda *_: called.append(True))
    assert called == []

    second = tmp_path / "second"
    second.mkdir()
    execution, _, _, _, _ = _execution(second)
    bad_metadata = (("model", "0" * 64, 5),)
    forged = replace(execution.preflight, artifact_metadata=bad_metadata)
    with pytest.raises(DaytonaExecutionError, match="preflight"):
        execute_daytona_job(replace(execution, preflight=forged), client_factory=lambda *_: called.append(True))
    assert called == []


def test_existing_local_download_destination_is_never_overwritten(tmp_path, monkeypatch):
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job
    import backend.app.daytona as adapter

    execution, client, _, _, _ = _execution(tmp_path)
    planted = execution.workspace / "planted"
    planted.mkdir()
    completion = planted / "completion-receipt.json"
    completion.write_bytes(b"do-not-overwrite")
    monkeypatch.setattr(adapter.tempfile, "mkdtemp", lambda **_: str(planted))
    with pytest.raises(DaytonaExecutionError, match="download"):
        execute_daytona_job(execution, client_factory=lambda *_: client)
    assert completion.read_bytes() == b"do-not-overwrite"
    assert len(client.delete_calls) == 1


def test_processor_download_uses_worker_size_ceiling(tmp_path, monkeypatch):
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job
    import backend.app.daytona as adapter

    execution, client, _, _, _ = _execution(tmp_path)
    monkeypatch.setattr(adapter, "MAX_PROCESSOR_RESULT_BYTES", 4)
    with pytest.raises(DaytonaExecutionError, match="size limit"):
        execute_daytona_job(execution, client_factory=lambda *_: client)
    assert len(client.delete_calls) == 1


def test_production_factory_passes_host_key_and_target_only_to_sdk_config(monkeypatch):
    from backend.app.daytona import _production_client_factory

    observed = {}
    class Config:
        def __init__(self, *, api_key, target):
            observed["config"] = {"api_key": api_key, "target": target}
    class Daytona:
        def __init__(self, config): observed["client_config"] = config
    fake = SimpleNamespace(DaytonaConfig=Config, Daytona=Daytona)
    monkeypatch.setitem(sys.modules, "daytona", fake)

    wrapped = _production_client_factory("host-secret", "us")

    assert observed["config"] == {"api_key": "host-secret", "target": "us"}
    assert wrapped._sdk is fake


@pytest.mark.parametrize("field", ["manifest_path", "evidence_path", "runtime_artifact"])
def test_symlinked_preflight_files_construct_no_client(tmp_path, field):
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job

    execution, _, _, _, _ = _execution(tmp_path)
    proof = execution.preflight
    if field == "runtime_artifact":
        _, target, container = proof.artifacts[0]
        link = tmp_path / "linked-model.bin"
        link.symlink_to(target)
        proof = replace(proof, artifacts=(("model", link, container),))
    else:
        target = getattr(proof, field)
        link = tmp_path / f"linked-{field}.json"
        link.symlink_to(target)
        proof = replace(proof, **{field: link})
    called = []

    with pytest.raises(DaytonaExecutionError, match="preflight"):
        execute_daytona_job(replace(execution, preflight=proof), client_factory=lambda *_: called.append(True))

    assert called == []


def test_cross_generation_envelope_is_rejected_before_artifact_download(tmp_path):
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job

    other = "f" * 32
    def mutate(remote):
        result_path = f"/home/daytona/job/result-bundle.json.generations/{GENERATION}/result.json"
        result = json.loads(remote[result_path])
        old_prefix = f"result-bundle.json.generations/{GENERATION}"
        new_prefix = f"result-bundle.json.generations/{other}"
        result["result"]["processorResultPath"] = f"{new_prefix}/result.processor-result.json"
        result["result"]["progressPath"] = f"{new_prefix}/result.progress.jsonl"
        for artifact in result["artifacts"]:
            artifact["relativePath"] = artifact["relativePath"].replace(old_prefix, new_prefix)
        result_bytes = canonical_json_bytes(result)
        remote[result_path] = result_bytes
        completion_path = "/home/daytona/job/completion-receipt.json"
        completion = json.loads(remote[completion_path])
        completion["resultSizeBytes"] = len(result_bytes)
        completion["resultSha256"] = hashlib.sha256(result_bytes).hexdigest()
        remote[completion_path] = canonical_json_bytes(completion)
        remote[f"/home/daytona/job/{new_prefix}/result.processor-result.json"] = b'{"detections":[]}'
        remote[f"/home/daytona/job/{new_prefix}/result.progress.jsonl"] = b""

    execution, client, sandbox, _, _ = _execution(tmp_path, remote_mutator=mutate)
    with pytest.raises(DaytonaExecutionError, match="download"):
        execute_daytona_job(execution, client_factory=lambda *_: client)

    assert [path for path, _ in sandbox.fs.downloads] == [
        "/home/daytona/job/completion-receipt.json",
        f"/home/daytona/job/result-bundle.json.generations/{GENERATION}/result.json",
    ]


def test_execution_diagnostics_are_deeply_immutable(tmp_path):
    from backend.app.daytona import DaytonaDiagnostics, DaytonaExecutionError, execute_daytona_job

    execution, client, _, _, _ = _execution(tmp_path)
    outcome = execute_daytona_job(execution, client_factory=lambda *_: client)

    assert type(outcome.diagnostics) is DaytonaDiagnostics
    with pytest.raises(FrozenInstanceError):
        outcome.diagnostics.stdout = "changed"  # type: ignore[misc]
    with pytest.raises(DaytonaExecutionError, match="result interface"):
        replace(outcome, diagnostics={"stdout": "changed"})  # type: ignore[arg-type]


@pytest.mark.parametrize("sandbox_id", ["secret", "access-token", "credential_123"])
def test_sensitive_sandbox_id_is_not_exposed_when_cleanup_fails(tmp_path, sandbox_id):
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job

    execution, client, _, _, _ = _execution(tmp_path, sandbox_id=sandbox_id)
    client.delete_errors = [RuntimeError("fail")] * 3

    with pytest.raises(DaytonaExecutionError, match="cleanup") as raised:
        execute_daytona_job(execution, client_factory=lambda *_: client)

    assert sandbox_id not in str(raised.value)
    assert len(client.delete_calls) == 3


def test_fifo_sealed_source_is_rejected_before_client_construction(tmp_path):
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job

    execution, client, _, _, _ = _execution(tmp_path)
    client.create_error = RuntimeError("must not create")
    source = execution.bundle_root / "source/source.tar"
    source.unlink()
    os.mkfifo(source)
    def write_fifo():
        try:
            source.write_bytes(b"source")
        except BrokenPipeError:
            pass
    writer = threading.Thread(target=write_fifo, daemon=True)
    writer.start()
    construct_calls = []

    def factory(*_):
        construct_calls.append(True)
        return client

    with pytest.raises(DaytonaExecutionError, match="preflight"):
        execute_daytona_job(execution, client_factory=factory)

    writer.join(timeout=1)
    assert construct_calls == []
    assert client.create_calls == []


def test_alternate_completion_namespace_is_rejected_before_result_download(tmp_path):
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job

    evil_relative = f"evil.json.generations/{GENERATION}/result.json"
    def mutate(remote):
        completion_path = "/home/daytona/job/completion-receipt.json"
        completion = json.loads(remote[completion_path])
        completion["resultPath"] = evil_relative
        remote[completion_path] = canonical_json_bytes(completion)
        original = f"/home/daytona/job/result-bundle.json.generations/{GENERATION}/result.json"
        remote[f"/home/daytona/job/{evil_relative}"] = remote[original]

    execution, client, sandbox, _, _ = _execution(tmp_path, remote_mutator=mutate)

    with pytest.raises(DaytonaExecutionError, match="download"):
        execute_daytona_job(execution, client_factory=lambda *_: client)

    assert [path for path, _ in sandbox.fs.downloads] == [
        "/home/daytona/job/completion-receipt.json"
    ]


def test_path_replacement_during_create_never_uploads_replacement_bytes(tmp_path):
    from backend.app.daytona import execute_daytona_job

    execution, client, sandbox, _, _ = _execution(tmp_path)
    source = execution.bundle_root / "source/source.tar"
    original_create = client.create
    def create(spec, timeout):
        source.unlink()
        source.write_bytes(b"SECRET")
        return original_create(spec, timeout)
    client.create = create

    outcome = execute_daytona_job(execution, client_factory=lambda *_: client)

    uploaded = {path: payload for path, payload, _ in sandbox.fs.uploads}
    assert uploaded["/home/daytona/job/source/source.tar"] == b"source"
    assert b"SECRET" not in uploaded.values()
    assert outcome.sandbox_id == "sb-123"


def test_fifo_replacement_during_create_does_not_reopen_or_block(tmp_path):
    from backend.app.daytona import execute_daytona_job

    execution, client, sandbox, _, _ = _execution(tmp_path)
    source = execution.bundle_root / "source/source.tar"
    original_create = client.create
    def create(spec, timeout):
        source.unlink()
        os.mkfifo(source)
        return original_create(spec, timeout)
    client.create = create
    captured = []
    def run():
        try:
            captured.append(execute_daytona_job(execution, client_factory=lambda *_: client))
        except Exception as exc:  # pragma: no cover - asserted through captured value
            captured.append(exc)
    runner = threading.Thread(target=run, daemon=True)
    runner.start()
    runner.join(timeout=0.5)
    finished_without_unblock = not runner.is_alive()
    if runner.is_alive():
        descriptor = os.open(source, os.O_WRONLY | os.O_NONBLOCK)
        try:
            os.write(descriptor, b"source")
        finally:
            os.close(descriptor)
        runner.join(timeout=1)

    assert finished_without_unblock
    assert not runner.is_alive()
    assert captured and not isinstance(captured[0], Exception)
    uploaded = {path: payload for path, payload, _ in sandbox.fs.uploads}
    assert uploaded["/home/daytona/job/source/source.tar"] == b"source"


def test_duplicate_proof_artifact_ids_with_unused_metadata_construct_no_client(tmp_path):
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job

    execution, _, _, _, values = _execution(tmp_path)
    request, receipt, _, _ = values
    second_path = execution.bundle_root / "models/model-2.bin"
    second_path.write_bytes(b"model")
    second_entry = _entry("runtime_artifact", "models/model-2.bin", b"model")
    expanded = JobReceipt(
        receipt.schema_version, receipt.source_commit, receipt.manifest_sha256,
        receipt.evidence_sha256, receipt.job_request_sha256,
        receipt.requested_runtime_options, receipt.files + (second_entry,),
    )
    (execution.bundle_root / request.receipt_path).write_bytes(
        canonical_json_bytes(expanded.to_mapping())
    )
    digest = hashlib.sha256(b"model").hexdigest()
    proof = replace(
        execution.preflight,
        artifacts=(
            ("duplicate", execution.bundle_root / "models/model.bin", "/app/models/model.bin"),
            ("duplicate", second_path, "/app/models/model-2.bin"),
        ),
        artifact_metadata=(("duplicate", digest, 5), ("unused", digest, 5)),
    )
    called = []

    with pytest.raises(DaytonaExecutionError, match="preflight"):
        execute_daytona_job(
            replace(execution, preflight=proof),
            client_factory=lambda *_: called.append(True),
        )

    assert called == []


@pytest.mark.parametrize("case", ["duplicate_metadata", "mismatched_sets"])
def test_invalid_preflight_artifact_metadata_ids_construct_no_client(tmp_path, case):
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job

    execution, _, _, _, _ = _execution(tmp_path)
    artifact_id, digest, size = execution.preflight.artifact_metadata[0]
    if case == "duplicate_metadata":
        metadata = ((artifact_id, digest, size), (artifact_id, digest, size))
    else:
        metadata = (("unused", digest, size),)
    proof = replace(execution.preflight, artifact_metadata=metadata)
    called = []

    with pytest.raises(DaytonaExecutionError, match="preflight"):
        execute_daytona_job(
            replace(execution, preflight=proof),
            client_factory=lambda *_: called.append(True),
        )

    assert called == []


@pytest.mark.parametrize("provider_stdout", ["hunter2", "sk-live-4J7uQ9mN2pR8"])
def test_arbitrary_provider_stdout_never_survives_diagnostics(tmp_path, provider_stdout):
    from backend.app.daytona import execute_daytona_job

    execution, client, sandbox, _, _ = _execution(tmp_path)
    sandbox.process.response.result = provider_stdout

    outcome = execute_daytona_job(execution, client_factory=lambda *_: client)

    assert provider_stdout not in outcome.diagnostics.stdout
    assert outcome.diagnostics.stdout == "[REDACTED]"


@pytest.mark.parametrize(
    "failure",
    ["malformed_completion", "oversize", "digest", "result_validation", "processor", "progress"],
)
def test_failed_result_collection_removes_exact_private_staging(tmp_path, monkeypatch, failure):
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job
    import backend.app.daytona as adapter

    def mutate(remote):
        completion_path = "/home/daytona/job/completion-receipt.json"
        result_path = f"/home/daytona/job/result-bundle.json.generations/{GENERATION}/result.json"
        if failure == "malformed_completion":
            remote[completion_path] = b"not-json"
        elif failure == "oversize":
            remote[completion_path] = b"x" * (4 * 1024 * 1024 + 1)
        elif failure == "digest":
            remote[result_path] = b"{}\n"
        elif failure == "result_validation":
            result = json.loads(remote[result_path])
            result["sourceCommit"] = "c" * 40
            payload = canonical_json_bytes(result)
            remote[result_path] = payload
            completion = json.loads(remote[completion_path])
            completion["resultSizeBytes"] = len(payload)
            completion["resultSha256"] = hashlib.sha256(payload).hexdigest()
            remote[completion_path] = canonical_json_bytes(completion)
        elif failure == "processor":
            remote.pop(f"/home/daytona/job/result-bundle.json.generations/{GENERATION}/result.processor-result.json")
        else:
            remote.pop(f"/home/daytona/job/result-bundle.json.generations/{GENERATION}/result.progress.jsonl")

    execution, client, _, _, _ = _execution(tmp_path, remote_mutator=mutate)
    created = []
    real_mkdtemp = adapter.tempfile.mkdtemp
    def tracked_mkdtemp(*args, **kwargs):
        path = Path(real_mkdtemp(*args, **kwargs))
        created.append(path)
        return str(path)
    monkeypatch.setattr(adapter.tempfile, "mkdtemp", tracked_mkdtemp)

    with pytest.raises(DaytonaExecutionError, match="download"):
        execute_daytona_job(execution, client_factory=lambda *_: client)

    result_staging = [path for path in created if path.name.startswith("daytona-result-")]
    assert len(result_staging) == 1
    assert not result_staging[0].exists()


def test_download_iterator_failure_removes_private_staging(tmp_path, monkeypatch):
    from backend.app.daytona import DaytonaExecutionError, execute_daytona_job
    import backend.app.daytona as adapter

    execution, client, sandbox, _, _ = _execution(tmp_path)
    original_download = sandbox.fs.download_file_stream
    completion_path = "/home/daytona/job/completion-receipt.json"
    def download(remote_path, timeout):
        if remote_path != completion_path:
            return original_download(remote_path, timeout)
        def failing():
            yield b"{"
            raise RuntimeError("stream failed")
        return failing()
    sandbox.fs.download_file_stream = download
    created = []
    real_mkdtemp = adapter.tempfile.mkdtemp
    def tracked_mkdtemp(*args, **kwargs):
        path = Path(real_mkdtemp(*args, **kwargs))
        created.append(path)
        return str(path)
    monkeypatch.setattr(adapter.tempfile, "mkdtemp", tracked_mkdtemp)

    with pytest.raises(DaytonaExecutionError, match="download"):
        execute_daytona_job(execution, client_factory=lambda *_: client)

    result_staging = [path for path in created if path.name.startswith("daytona-result-")]
    assert len(result_staging) == 1
    assert not result_staging[0].exists()


@pytest.mark.parametrize("abort", [False, True])
def test_download_explicitly_closes_provider_iterator_on_exhaustion_or_abort(tmp_path, abort):
    from backend.app.daytona import DaytonaExecutionError, _download

    class TrackingIterator:
        def __init__(self):
            self.items = iter((b"12345",))
            self.closed = False
        def __iter__(self): return self
        def __next__(self): return next(self.items)
        def close(self):
            self.closed = True
            if abort:
                raise RuntimeError("close failure")
    iterator = TrackingIterator()
    class FS:
        def download_file_stream(self, remote_path, timeout):
            return iterator
    destination = tmp_path / "download.bin"

    if abort:
        with pytest.raises(DaytonaExecutionError, match="size limit"):
            _download(FS(), "/remote", destination, timeout=1, maximum=4)
    else:
        _download(FS(), "/remote", destination, timeout=1, maximum=5)

    assert iterator.closed


@pytest.mark.parametrize("failure", [None, "not_found", "other"])
def test_sdk_delete_forwards_and_only_maps_confirmed_not_found(failure):
    from backend.app.daytona import DaytonaConfirmedAbsent, _SdkClient

    class NotFound(Exception): pass
    SDK = SimpleNamespace(DaytonaNotFoundError=NotFound)
    expected = RuntimeError("other")
    class Raw:
        def __init__(self): self.calls = []
        def delete(self, sandbox, *, timeout, wait):
            self.calls.append((sandbox, timeout, wait))
            if failure == "not_found": raise NotFound()
            if failure == "other": raise expected
    raw = Raw()
    sandbox = object()
    adapter = _SdkClient(raw, SDK)

    if failure == "not_found":
        with pytest.raises(DaytonaConfirmedAbsent):
            adapter.delete(sandbox, 120, True)
    elif failure == "other":
        with pytest.raises(RuntimeError) as raised:
            adapter.delete(sandbox, 120, True)
        assert raised.value is expected
    else:
        adapter.delete(sandbox, 120, True)

    assert raw.calls == [(sandbox, 120, True)]


def test_sdk_get_is_bounded_and_only_maps_confirmed_not_found():
    from backend.app.daytona import DaytonaConfirmedAbsent, _SdkClient

    class NotFound(Exception): pass
    SDK = SimpleNamespace(DaytonaNotFoundError=NotFound)
    sandbox = object()
    class Raw:
        def __init__(self): self.calls = []; self.failure = None
        def get(self, sandbox_id, *, request_timeout):
            self.calls.append((sandbox_id, request_timeout))
            if self.failure: raise self.failure
            return sandbox
    raw = Raw()
    adapter = _SdkClient(raw, SDK)

    assert adapter.get("sandbox-1", 17) is sandbox
    raw.failure = NotFound()
    with pytest.raises(DaytonaConfirmedAbsent):
        adapter.get("sandbox-1", 17)
    expected = RuntimeError("other")
    raw.failure = expected
    with pytest.raises(RuntimeError) as raised:
        adapter.get("sandbox-1", 17)
    assert raised.value is expected
    assert raw.calls == [("sandbox-1", 17)] * 3


def _sdk_create_failure_adapter(
    monkeypatch, *, candidate=None, lookup_error=None, cleanup_fails=False
):
    from backend.app.daytona import DaytonaSandboxSpec, _SdkClient
    import backend.app.daytona as adapter

    class NotFound(Exception): pass
    class Resources:
        def __init__(self, **values): self.values = values
    class Params:
        def __init__(self, **values): self.values = values
    class GpuType:
        RTX_PRO_6000 = "rtx"
        H100 = "h100"
    SDK = SimpleNamespace(
        Resources=Resources,
        CreateSandboxFromImageParams=Params,
        GpuType=GpuType,
        DaytonaNotFoundError=NotFound,
    )
    create_error = RuntimeError("create failed")

    class Raw:
        def __init__(self):
            self.params = None
            self.allocated = None
            self.gets = []
            self.deletes = []

        def create(self, params, *, timeout):
            self.params = params
            self.allocated = candidate
            raise create_error

        def get(self, sandbox_id, *, request_timeout):
            self.gets.append((sandbox_id, request_timeout))
            if len(self.gets) == 1:
                if lookup_error is not None:
                    raise lookup_error
                if candidate is not None:
                    return candidate
            if cleanup_fails:
                raise RuntimeError("provider-secret")
            raise NotFound()

        def delete(self, sandbox, *, timeout, wait):
            self.deletes.append((sandbox, timeout, wait))
            if cleanup_fails:
                raise RuntimeError("provider-secret")

    def deterministic_urandom(size):
        assert size == 16
        return b"\xab" * size

    monkeypatch.setattr(adapter.os, "urandom", deterministic_urandom)
    raw = Raw()
    spec = DaytonaSandboxSpec(
        "policy", False, True, False, 45, True, (), 4, 8, 10, 1,
        ("RTX-PRO-6000", "H100"),
    )
    return _SdkClient(raw, SDK), raw, spec, create_error


def test_sdk_create_owned_allocation_is_recovered_by_exact_name(monkeypatch):
    from backend.app.daytona import _SDK_NAME_PREFIX, _SDK_OWNER_LABEL

    token = "ab" * 16
    name = f"{_SDK_NAME_PREFIX}{token}"
    candidate = SimpleNamespace(
        id="sandbox-id", name=name, labels={_SDK_OWNER_LABEL: token}
    )
    adapter, raw, spec, create_error = _sdk_create_failure_adapter(
        monkeypatch, candidate=candidate
    )

    with pytest.raises(RuntimeError) as raised:
        adapter.create(spec, 600)

    assert raised.value is create_error
    assert raw.params.values["name"] == name
    assert raw.params.values["labels"] == {_SDK_OWNER_LABEL: token}
    assert raw.gets == [(name, 600), ("sandbox-id", 600)]
    assert raw.deletes == [(candidate, 600, True)]


def test_sdk_create_absent_allocation_preserves_original_failure(monkeypatch):
    adapter, raw, spec, create_error = _sdk_create_failure_adapter(monkeypatch)

    with pytest.raises(RuntimeError) as raised:
        adapter.create(spec, 600)

    assert raised.value is create_error
    assert raised.value.__suppress_context__ is True
    assert raw.gets == [(f"fa-{'ab' * 16}", 600)]
    assert raw.deletes == []


@pytest.mark.parametrize(
    "candidate",
    (
        SimpleNamespace(
            id="sandbox-id",
            name=f"fa-{'ab' * 16}",
            labels={"football-analyst-owner": "wrong"},
        ),
        SimpleNamespace(
            id="sandbox-id",
            name="fa-wrong",
            labels={"football-analyst-owner": "ab" * 16},
        ),
        SimpleNamespace(
            id="sandbox-id",
            name=f"fa-{'ab' * 16}",
            labels=None,
        ),
        SimpleNamespace(
            id="sandbox-id",
            name=f"fa-{'ab' * 16}",
            labels={},
        ),
        SimpleNamespace(
            id="sandbox-id",
            labels={"football-analyst-owner": "ab" * 16},
        ),
    ),
    ids=("wrong-label", "wrong-name", "null-labels", "empty-labels", "missing-name"),
)
def test_sdk_create_unowned_candidate_refuses_deletion(monkeypatch, candidate):
    from backend.app.daytona import DaytonaExecutionError

    adapter, raw, spec, _ = _sdk_create_failure_adapter(
        monkeypatch, candidate=candidate
    )

    with pytest.raises(DaytonaExecutionError) as raised:
        adapter.create(spec, 600)

    assert str(raised.value) == "create: sandbox cleanup was not confirmed"
    assert "provider-secret" not in str(raised.value)
    assert raw.deletes == []


def test_sdk_create_inconclusive_lookup_refuses_deletion_without_secret(monkeypatch):
    from backend.app.daytona import DaytonaExecutionError

    adapter, raw, spec, _ = _sdk_create_failure_adapter(
        monkeypatch,
        candidate=SimpleNamespace(
            id="sandbox-id",
            name=f"fa-{'ab' * 16}",
            labels={"football-analyst-owner": "ab" * 16},
        ),
        lookup_error=RuntimeError("provider-secret"),
    )

    with pytest.raises(DaytonaExecutionError) as raised:
        adapter.create(spec, 600)

    assert str(raised.value) == "create: sandbox cleanup was not confirmed"
    assert "secret" not in str(raised.value)
    assert raw.deletes == []


def test_sdk_create_owned_allocation_exposes_handle_when_cleanup_unconfirmed(monkeypatch):
    from backend.app.daytona import _UnreturnedSandboxCleanupError

    candidate = SimpleNamespace(
        id="sandbox-id",
        name=f"fa-{'ab' * 16}",
        labels={"football-analyst-owner": "ab" * 16},
    )
    adapter, raw, spec, _ = _sdk_create_failure_adapter(
        monkeypatch, candidate=candidate, cleanup_fails=True
    )

    with pytest.raises(_UnreturnedSandboxCleanupError) as raised:
        adapter.create(spec, 600)

    assert str(raised.value) == "create: sandbox cleanup was not confirmed"
    assert raised.value.sandbox is candidate
    assert raw.deletes == [(candidate, 600, True)] * 3
    assert raw.gets == [(f"fa-{'ab' * 16}", 600)] + [("sandbox-id", 600)] * 3


def test_sdk_create_uses_explicit_image_override():
    from backend.app.daytona import DaytonaSandboxSpec, _SdkClient

    class Resources:
        def __init__(self, **values): self.values = values
    class Params:
        def __init__(self, **values): self.values = values
    class GpuType:
        RTX_PRO_6000 = "rtx"
        H100 = "h100"
    SDK = SimpleNamespace(Resources=Resources, CreateSandboxFromImageParams=Params,
                          GpuType=GpuType, DaytonaNotFoundError=LookupError)
    class Raw:
        def create(self, params, *, timeout): self.params = params; return object()
    raw = Raw()
    image = object()
    spec = DaytonaSandboxSpec("policy-image", False, True, False, 45, True, (), 4, 8, 10, 1, ("RTX-PRO-6000", "H100"))
    _SdkClient(raw, SDK, image=image).create(spec, 600)
    assert raw.params.values["image"] is image


def test_sdk_image_factory_context_lives_through_create_and_always_cleans():
    from contextlib import contextmanager
    from backend.app.daytona import DaytonaSandboxSpec, _SdkClient

    live = []
    image = object()
    @contextmanager
    def image_factory():
        live.append(True)
        try: yield image
        finally: live.clear()
    class Resources:
        def __init__(self, **values): pass
    class Params:
        def __init__(self, **values): self.image = values["image"]
    class GpuType:
        RTX_PRO_6000 = "rtx"; H100 = "h100"
    SDK = SimpleNamespace(Resources=Resources, CreateSandboxFromImageParams=Params,
                          GpuType=GpuType, DaytonaNotFoundError=LookupError)
    class Raw:
        def create(self, params, *, timeout):
            assert live and params.image is image
            raise RuntimeError("create failed")
        def get(self, sandbox_id, *, request_timeout):
            raise LookupError()
    spec = DaytonaSandboxSpec("policy", False, True, False, 45, True, (), 4, 8, 10, 1, ("RTX-PRO-6000", "H100"))
    with pytest.raises(RuntimeError, match="create failed"):
        _SdkClient(Raw(), SDK, image_factory=image_factory).create(spec, 600)
    assert live == []


@pytest.mark.parametrize("delete_fails", [False, True])
def test_sdk_create_cleans_raw_sandbox_when_image_context_exit_fails(delete_fails):
    from backend.app.daytona import (
        DaytonaSandboxSpec, _SdkClient,
        _UnreturnedSandboxCleanupError,
    )

    sandbox = SimpleNamespace(id="sandbox-1")
    context_error = RuntimeError("context-secret")

    class ImageContext:
        def __enter__(self):
            return object()

        def __exit__(self, *_):
            raise context_error

    class Resources:
        def __init__(self, **values): pass
    class Params:
        def __init__(self, **values): pass
    class GpuType:
        RTX_PRO_6000 = "rtx"; H100 = "h100"
    SDK = SimpleNamespace(Resources=Resources, CreateSandboxFromImageParams=Params,
                          GpuType=GpuType, DaytonaNotFoundError=LookupError)
    class Raw:
        def __init__(self): self.deleted = []; self.gets = []
        def create(self, params, *, timeout): return sandbox
        def delete(self, target, *, timeout, wait):
            self.deleted.append((target, timeout, wait))
            if delete_fails:
                raise RuntimeError("provider-secret")
        def get(self, sandbox_id, *, request_timeout):
            self.gets.append((sandbox_id, request_timeout))
            if delete_fails:
                raise RuntimeError("provider-secret")
            raise LookupError()

    raw = Raw()
    adapter = _SdkClient(raw, SDK, image_factory=ImageContext)
    spec = DaytonaSandboxSpec("policy", False, True, False, 45, True, (), 4, 8, 10, 1,
                              ("RTX-PRO-6000", "H100"))
    if delete_fails:
        with pytest.raises(_UnreturnedSandboxCleanupError) as raised:
            adapter.create(spec, 600)
        assert str(raised.value) == "create: sandbox cleanup was not confirmed"
        assert raised.value.sandbox is sandbox
        assert "secret" not in str(raised.value)
    else:
        with pytest.raises(RuntimeError) as raised:
            adapter.create(spec, 600)
        assert raised.value is context_error
    expected_calls = 3 if delete_fails else 1
    assert raw.deleted == [(sandbox, 600, True)] * expected_calls
    assert raw.gets == [("sandbox-1", 600)] * expected_calls


def test_sdk_create_emergency_cleanup_retries_transient_delete_and_get_failures():
    from backend.app.daytona import DaytonaSandboxSpec, _SdkClient

    sandbox = SimpleNamespace(id="sandbox-1")
    context_error = RuntimeError("context changed")
    class ImageContext:
        def __enter__(self): return object()
        def __exit__(self, *_): raise context_error
    class Resources:
        def __init__(self, **values): pass
    class Params:
        def __init__(self, **values): pass
    class GpuType:
        RTX_PRO_6000 = "rtx"; H100 = "h100"
    SDK = SimpleNamespace(Resources=Resources, CreateSandboxFromImageParams=Params,
                          GpuType=GpuType, DaytonaNotFoundError=LookupError)
    class Raw:
        def __init__(self): self.deletes = []; self.gets = []
        def create(self, params, *, timeout): return sandbox
        def delete(self, target, *, timeout, wait):
            self.deletes.append((target, timeout, wait))
            if len(self.deletes) == 1: raise RuntimeError("transient delete")
        def get(self, sandbox_id, *, request_timeout):
            self.gets.append((sandbox_id, request_timeout))
            if len(self.gets) == 1: raise RuntimeError("transient get")
            raise LookupError()

    raw = Raw()
    spec = DaytonaSandboxSpec("policy", False, True, False, 45, True, (), 4, 8, 10, 1,
                              ("RTX-PRO-6000", "H100"))
    with pytest.raises(RuntimeError) as raised:
        _SdkClient(raw, SDK, image_factory=ImageContext).create(spec, 600)

    assert raised.value is context_error
    assert raw.deletes == [(sandbox, 600, True)] * 2
    assert raw.gets == [("sandbox-1", 600)] * 2
