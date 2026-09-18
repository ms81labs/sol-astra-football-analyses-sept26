from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess

import pytest

from backend.scripts import run_daytona_gpu_smoke as smoke
from backend.release.evidence import RemoteExecution


ROOT = Path(__file__).resolve().parents[2]
_REAL_RELEASE_BINDING = smoke._release_binding


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _receipt_bound_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "smoke-tests@example.invalid")
    _git(root, "config", "user.name", "Smoke Tests")
    (root / ".gitignore").write_text(".verification/\n")
    worker = root / "backend/app/processor.py"
    worker.parent.mkdir(parents=True)
    worker.write_text("VERSION = 1\n")
    _git(root, "add", ".gitignore", "backend/app/processor.py")
    _git(root, "commit", "-m", "source")
    source_commit = _git(root, "rev-parse", "HEAD")

    manifest = json.loads((ROOT / "backend/release/v7.3.json").read_text())
    manifest["sourceCommit"] = source_commit
    manifest_path = root / "backend/release/v7.3.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    _git(root, "add", "backend/release/v7.3.json")
    _git(root, "commit", "-m", "release manifest")

    from backend.release.evidence import REQUIRED_GATE_COMMANDS
    from backend.scripts.write_verification_evidence import record_verifier_success

    logs = root / ".verification/logs"
    logs.mkdir(parents=True)
    now = datetime.now(timezone.utc)
    base = (now - timedelta(seconds=len(REQUIRED_GATE_COMMANDS) + 2)).timestamp()
    for index, name in enumerate(tuple(REQUIRED_GATE_COMMANDS)[:-1]):
        log = logs / f"{name}.log"
        log.write_text(f"{name} passed\n")
        os.utime(log, (base + index, base + index))
    record_verifier_success(root, now=now)
    return root


@pytest.fixture(autouse=True)
def _stable_release_binding(monkeypatch):
    monkeypatch.setattr(smoke, "_release_binding", lambda root: ({
        "sourceCommit": "a" * 40, "verificationCommit": "b" * 40,
        "manifestSha256": "c" * 64,
    }, smoke.datetime(2000, 1, 1, tzinfo=smoke.timezone.utc)))


def test_dry_run_validates_committed_environment_without_loading_sdk(monkeypatch):
    imported = []
    monkeypatch.setattr(smoke.importlib, "import_module", lambda name: imported.append(name))
    report = smoke.run_dry_run(ROOT)
    assert report["mode"] == "dry-run"
    assert report["sdkVersion"] == "0.207.0"
    assert report["gpuTypes"] == ["RTX-PRO-6000", "H100"]
    assert imported == []


def test_cli_success_emits_canonical_utf8_json_bytes(monkeypatch, capfdbinary):
    report = {"mode": "dry-run", "observedGpu": "Málaga ⚽"}
    monkeypatch.setattr(smoke, "run_dry_run", lambda _: report)

    assert smoke.main(["--dry-run"]) == 0
    captured = capfdbinary.readouterr()
    assert captured.out == smoke.canonical_json_bytes(report)
    assert "Málaga ⚽".encode() in captured.out
    assert b"\\u" not in captured.out
    assert captured.err == b""


@pytest.mark.parametrize("verify,allow", [("0", "0"), ("1", "0"), ("0", "1"), ("yes", "1")])
def test_real_smoke_rejects_before_client_construction(verify, allow):
    calls = []
    with pytest.raises(smoke.SmokeError, match="authorization"):
        smoke.run_real_smoke(
            ROOT,
            env={"VERIFY_DAYTONA": verify, "ALLOW_DAYTONA_MUTATION": allow, "DAYTONA_API_KEY": "secret"},
            client_factory=lambda *_: calls.append(True),
        )
    assert calls == []


def test_cli_modes_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        smoke._parser().parse_args(["--dry-run", "--real-smoke"])


def test_environment_rejects_unhashed_unpinned_duplicate_provider_and_changed_base(tmp_path):
    worker = tmp_path / "backend/daytona_worker"
    worker.mkdir(parents=True)
    fixture = tmp_path / "backend/tests/fixtures/daytona"
    fixture.mkdir(parents=True)
    (tmp_path / "backend/requirements-runtime.txt").write_text("daytona==0.207.0\n")
    (fixture / "job-request.json").write_text('{"config":{},"inputVideoPath":"input.mp4","jobId":"smoke-job","matchId":"smoke-match","receiptPath":"receipt.json","schemaVersion":1}\n')
    good_docker = smoke.expected_dockerfile()
    (worker / "Dockerfile").write_text(good_docker)
    direct = (ROOT / "backend/daytona_worker/requirements.txt").read_text()
    exact_lock = (ROOT / "backend/daytona_worker/requirements.lock").read_text()
    (worker / "requirements.txt").write_text(direct)
    lock = worker / "requirements.lock"
    lock.write_text(exact_lock)
    smoke.validate_worker_environment(tmp_path)

    for bad in ("numpy\n", "numpy==2.4.2\n", "numpy==2.4.2 --hash=sha256:\n"):
        lock.write_text(bad)
        with pytest.raises(smoke.SmokeError):
            smoke.validate_worker_environment(tmp_path)
    lock.write_text("opencv-python==4.13.0.92 --hash=sha256:" + "a" * 64 + "\nopencv-python-headless==4.13.0.92 --hash=sha256:" + "b" * 64 + "\n")
    with pytest.raises(smoke.SmokeError, match="exact lock"):
        smoke.validate_worker_environment(tmp_path)
    lock.write_text(exact_lock)
    (worker / "Dockerfile").write_text(good_docker.replace(smoke.IMAGE, smoke.IMAGE[:-1] + "0"))
    with pytest.raises(smoke.SmokeError, match="Dockerfile"):
        smoke.validate_worker_environment(tmp_path)


def test_worker_requirement_pins_remain_aligned_with_cuda_profile():
    direct = (ROOT / "backend/daytona_worker/requirements.txt").read_text()
    profile_pins = {
        line.split(";", 1)[0].strip()
        for profile in ("cpu-cv.in", "cuda.in")
        for line in (ROOT / "backend/requirements" / profile).read_text().splitlines()
        if line and not line.startswith(("#", "-r"))
    }
    # PyYAML supports the local training gate and is not needed in the sealed worker.
    profile_pins.discard("pyyaml==6.0.3")
    assert "pandas==3.0.1\n" in direct
    assert "boto3==1.34.131\n" in direct
    assert "pydantic==2.13.5\n" in direct
    pins = {line for line in direct.splitlines() if line and not line.startswith("#")}
    assert profile_pins <= pins
    locked = {
        line.split(" --hash=", 1)[0]
        for line in (ROOT / "backend/daytona_worker/requirements.lock").read_text().splitlines()
    }
    assert pins < locked
    assert {
        "botocore==1.34.162",
        "contourpy==1.3.3",
        "pydantic-core==2.46.5",
        "requests==2.34.2",
    } <= locked
    assert all(" --hash=sha256:" in line for line in (ROOT / "backend/daytona_worker/requirements.lock").read_text().splitlines())


def test_worker_probe_loads_production_closure_and_executes_cuda():
    assert "backend.app.processor" in smoke.WORKER_IMPORT_COMMAND
    assert "backend.app.proof_runtime" in smoke.WORKER_IMPORT_COMMAND
    assert "torch.cuda.is_available()" in smoke.WORKER_IMPORT_COMMAND
    assert "device='cuda'" in smoke.WORKER_IMPORT_COMMAND


def test_worker_image_removes_incompatible_base_audio_before_locked_install():
    dockerfile = (ROOT / "backend/daytona_worker/Dockerfile").read_text()
    expected = (
        "RUN python -m pip uninstall --yes torchaudio \\\n"
        " && python -m pip install --require-hashes --no-deps -r /tmp/requirements.lock \\\n"
        " && python -m pip check\n"
    )
    assert expected in dockerfile
    assert smoke.expected_dockerfile() == dockerfile


def test_worker_image_closes_opencv_headless_runtime():
    dockerfile = (ROOT / "backend/daytona_worker/Dockerfile").read_text()
    expected = (
        "RUN apt-get update \\\n"
        " && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \\\n"
        "      libgl1 libglib2.0-0 libxcb1 \\\n"
        " && rm -rf /var/lib/apt/lists/*\n"
        "ENV QT_QPA_PLATFORM=offscreen\n"
    )
    assert expected in dockerfile
    assert smoke.expected_dockerfile() == dockerfile


def test_worker_image_contains_the_tracker_compatibility_module():
    dockerfile = (ROOT / "backend/daytona_worker/Dockerfile").read_text()
    assert "lap.py" in smoke.WORKER_CONTEXT_MEMBERS
    assert "COPY lap.py /workspace/lap.py\n" in dockerfile
    assert "YOLO_AUTOINSTALL=false" in dockerfile
    assert "PYTHONPATH=/workspace" in dockerfile
    assert "from ultralytics.trackers.utils import matching" in smoke.WORKER_IMPORT_COMMAND
    assert "matching.lap is lap" in smoke.WORKER_IMPORT_COMMAND
    assert smoke.expected_dockerfile() == dockerfile


class _Response:
    def __init__(self, result="", exit_code=0, stderr=""):
        self.result, self.exit_code, self.stderr = result, exit_code, stderr


class _FS:
    def __init__(self): self.uploads = []; self.downloads = []; self.files = {}
    def upload_file_stream(self, source, remote_path, timeout):
        chunks = []
        while chunk := source.read(7): chunks.append(chunk)
        payload = b"".join(chunks)
        self.uploads.append((remote_path, payload, timeout))
        self.files[remote_path] = payload
    def download_file_stream(self, remote_path, timeout):
        self.downloads.append((remote_path, timeout))
        yield self.files[remote_path]


class _Process:
    def __init__(self, fs): self.commands = []; self.fs = fs
    def exec(self, command, **kwargs):
        self.commands.append((command, kwargs))
        if command == smoke.SMOKE_COMMAND:
            result = smoke.canonical_json_bytes({"jobId": "smoke-job", "matchId": "smoke-match", "status": "passed"})
            self.fs.files[smoke.RESULT_PATH] = result
            self.fs.files[smoke.COMPLETION_PATH] = smoke.canonical_json_bytes({
                "jobId": "smoke-job", "matchId": "smoke-match", "resultPath": smoke.RESULT_PATH,
                "resultSizeBytes": len(result), "resultSha256": smoke.hashlib.sha256(result).hexdigest(),
            })
        return _Response("NVIDIA H100" if command == "nvidia-smi --query-gpu=name --format=csv,noheader" else "")


class _Sandbox:
    id = "sandbox-1"
    def __init__(self):
        self.fs = _FS()
        self.process = _Process(self.fs)


class _Client:
    def __init__(self, *, absent=True):
        self.created = []; self.deleted = []; self.absent = absent; self.sandbox = _Sandbox()
        self.worker_context_sha256 = "d" * 64
    def create(self, spec, timeout): self.created.append((spec, timeout)); return self.sandbox
    def delete(self, sandbox, timeout, wait): self.deleted.append((sandbox.id, timeout, wait))
    def get(self, sandbox_id, timeout):
        if self.absent: raise smoke.DaytonaConfirmedAbsent()
        return self.sandbox


def test_fake_real_smoke_creates_once_streams_checks_and_confirms_deletion(monkeypatch):
    client = _Client()
    report = smoke.run_real_smoke(
        ROOT,
        env={"VERIFY_DAYTONA": "1", "ALLOW_DAYTONA_MUTATION": "1", "DAYTONA_API_KEY": "secret"},
        client_factory=lambda key, target: client,
    )
    assert len(client.created) == 1
    spec = client.created[0][0]
    assert spec.gpu_types == ("RTX-PRO-6000", "H100")
    assert [item[0] for item in client.sandbox.process.commands] == [
        "nvidia-smi --query-gpu=name --format=csv,noheader",
        "mkdir -p /home/daytona/smoke",
        smoke.WORKER_IMPORT_COMMAND,
        smoke.SMOKE_COMMAND,
    ]
    assert len(client.sandbox.fs.uploads) == 1
    assert [item[0] for item in client.sandbox.fs.downloads] == [smoke.RESULT_PATH, smoke.COMPLETION_PATH]
    assert client.deleted
    assert report["requestedGpuOrder"] == ["RTX-PRO-6000", "H100"]
    assert report["observedGpu"] == "H100"
    assert [item["command"] for item in report["commandResults"]] == ["nvidia-smi", "worker-import", "bounded-fixture"]
    assert [item["name"] for item in report["downloads"]] == ["result.json", "completion.json"]
    assert report["deletionConfirmed"] is True
    assert report["runpodMutationOccurred"] is False
    assert report["registryMutationOccurred"] is False
    assert {key: report[key] for key in (
        "sourceCommit", "verificationCommit", "manifestSha256", "workerContextSha256"
    )} == {"sourceCommit": "a" * 40, "verificationCommit": "b" * 40,
          "manifestSha256": "c" * 64, "workerContextSha256": "d" * 64}
    RemoteExecution.from_mapping(report)


def test_successful_remote_command_redacts_exact_host_api_key():
    api_key = "opaque-success-key-sentinel"
    client = _Client()
    original = client.sandbox.process.exec

    def leak_import(command, **kwargs):
        if command == smoke.WORKER_IMPORT_COMMAND:
            return _Response(f"loaded with {api_key}", 0, f"warning: {api_key}")
        return original(command, **kwargs)

    client.sandbox.process.exec = leak_import
    report = smoke.run_real_smoke(
        ROOT,
        env={"VERIFY_DAYTONA": "1", "ALLOW_DAYTONA_MUTATION": "1",
             "DAYTONA_API_KEY": api_key},
        client_factory=lambda *_: client,
    )

    rendered = json.dumps(report, sort_keys=True, separators=(",", ":"))
    assert api_key not in rendered
    RemoteExecution.from_mapping(report)
    assert client.deleted


def test_successful_remote_command_redaction_preserves_output_bound():
    api_key = "secret"
    supplied = api_key * 682 + "tail"
    sandbox = _Sandbox()
    sandbox.process.exec = lambda *_args, **_kwargs: _Response(supplied)

    returned, persisted = smoke._exec(
        sandbox, "successful-command", "boundary", 1, api_key=api_key
    )

    assert len(supplied) == 4096
    assert len(returned) <= 4096
    assert len(persisted["stdout"]) <= 4096
    assert api_key not in returned
    assert api_key not in persisted["stdout"]
    assert returned == persisted["stdout"]


def test_successful_remote_command_sanitizing_cannot_reconstruct_api_key():
    api_key = "opaque-success-key-sentinel"
    supplied = "opaque-" + api_key + "success-key-sentinel"
    sandbox = _Sandbox()
    sandbox.process.exec = lambda *_args, **_kwargs: _Response(supplied, 0, supplied)

    returned, persisted = smoke._exec(
        sandbox, "successful-command", "reconstruction", 1, api_key=api_key
    )

    assert returned == persisted["stdout"] == ""
    assert persisted["stderr"] == ""
    assert api_key not in returned
    assert api_key not in persisted["stdout"]
    assert api_key not in persisted["stderr"]


def test_deleted_timestamp_is_recorded_only_after_absence_is_confirmed(monkeypatch):
    client = _Client()
    emitted = []
    values = iter([
        "2026-09-08T12:00:00Z", "2026-09-08T12:00:01Z",
        "2026-09-08T12:00:02Z", "2026-09-08T12:00:03Z",
    ])

    def timestamp():
        value = next(values)
        emitted.append(value)
        return value

    def confirmed_absent(*_):
        assert len(emitted) == 3
        return True

    monkeypatch.setattr(smoke, "_timestamp", timestamp)
    monkeypatch.setattr(smoke, "_confirmed_absent", confirmed_absent)
    report = smoke.run_real_smoke(
        ROOT,
        env={"VERIFY_DAYTONA": "1", "ALLOW_DAYTONA_MUTATION": "1",
             "DAYTONA_API_KEY": "test-key"},
        client_factory=lambda *_: client,
    )

    assert report["deletedAt"] == "2026-09-08T12:00:03Z"


@pytest.mark.parametrize("committed", [False, True])
def test_release_binding_rejects_dirty_or_post_manifest_worker_before_create(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, committed: bool
) -> None:
    root = _receipt_bound_repo(tmp_path)
    worker = root / "backend/app/processor.py"
    worker.write_text("VERSION = 2\n")
    if committed:
        _git(root, "add", "backend/app/processor.py")
        _git(root, "commit", "-m", "forbidden worker change")
    calls = []
    monkeypatch.setattr(smoke, "_release_binding", _REAL_RELEASE_BINDING)
    monkeypatch.setattr(smoke, "validate_worker_environment", lambda _: smoke.load_daytona_policy())

    with pytest.raises(smoke.SmokeError, match="release verification binding"):
        smoke.run_real_smoke(
            root,
            env={"VERIFY_DAYTONA": "1", "ALLOW_DAYTONA_MUTATION": "1",
                 "DAYTONA_API_KEY": "test-key"},
            client_factory=lambda *_: calls.append(True),
        )

    assert calls == []


def test_cli_normalizes_release_binding_failure_without_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("VERIFY_DAYTONA", "1")
    monkeypatch.setenv("ALLOW_DAYTONA_MUTATION", "1")
    monkeypatch.setenv("DAYTONA_API_KEY", "test-key")
    monkeypatch.setattr(
        smoke, "_release_binding",
        lambda _: (_ for _ in ()).throw(smoke.PreflightError("sensitive path")),
    )

    assert smoke.main(["--real-smoke"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "release verification binding is invalid\n"
    assert "Traceback" not in captured.err


def test_nonzero_remote_command_preserves_bounded_sanitized_diagnostics_after_confirmed_cleanup():
    api_key = "opaque-host-key-sentinel"
    client = _Client()
    original = client.sandbox.process.exec
    def fail_import(command, **kwargs):
        if command == smoke.WORKER_IMPORT_COMMAND:
            return _Response(api_key + "x" * 10_000, 9, "Bearer provider-secret")
        return original(command, **kwargs)
    client.sandbox.process.exec = fail_import
    with pytest.raises(smoke.SmokeCommandError) as raised:
        smoke.run_real_smoke(
            ROOT,
            env={"VERIFY_DAYTONA": "1", "ALLOW_DAYTONA_MUTATION": "1", "DAYTONA_API_KEY": api_key},
            client_factory=lambda *_: client,
        )
    result = raised.value.command_result
    rendered = json.dumps(result, sort_keys=True, separators=(",", ":"))
    assert result["stage"] == "worker-import"
    assert result["exitCode"] == 9
    assert len(rendered) <= smoke.MAX_FAILURE_DIAGNOSTIC_CHARS
    assert "[REDACTED]" in rendered and "[TRUNCATED]" in rendered
    assert api_key not in rendered and "provider-secret" not in rendered
    assert api_key not in repr(raised.value) and "provider-secret" not in repr(raised.value)
    assert client.deleted


def test_failed_command_rejects_hostile_string_subclass_without_invoking_it_after_cleanup():
    calls = []

    class HostileStr(str):
        def __str__(self):
            calls.append("__str__")
            raise AssertionError("custom __str__ called")

        def replace(self, *_args, **_kwargs):
            calls.append("replace")
            raise AssertionError("custom replace called")

    supplied = "hostile-value-should-not-escape"
    client = _Client()
    original = client.sandbox.process.exec

    def fail_import(command, **kwargs):
        if command == smoke.WORKER_IMPORT_COMMAND:
            return _Response(HostileStr(supplied), 9)
        return original(command, **kwargs)

    client.sandbox.process.exec = fail_import
    with pytest.raises(smoke.SmokeCommandError) as raised:
        smoke.run_real_smoke(
            ROOT,
            env={"VERIFY_DAYTONA": "1", "ALLOW_DAYTONA_MUTATION": "1",
                 "DAYTONA_API_KEY": "opaque-host-key-sentinel"},
            client_factory=lambda *_: client,
        )

    assert raised.value.command_result["stdout"] == "[UNAVAILABLE]"
    assert supplied not in repr(raised.value)
    assert calls == []
    assert client.deleted


def test_oversized_exit_code_is_generic_after_cleanup_and_emits_no_failure_json(
    monkeypatch, capsys
):
    supplied = "remote-output-should-not-escape"
    client = _Client()
    original = client.sandbox.process.exec

    def fail_import(command, **kwargs):
        if command == smoke.WORKER_IMPORT_COMMAND:
            return _Response(supplied, 10 ** 10_000)
        return original(command, **kwargs)

    client.sandbox.process.exec = fail_import
    with pytest.raises(smoke.SmokeError) as raised:
        smoke.run_real_smoke(
            ROOT,
            env={"VERIFY_DAYTONA": "1", "ALLOW_DAYTONA_MUTATION": "1",
                 "DAYTONA_API_KEY": "opaque-host-key-sentinel"},
            client_factory=lambda *_: client,
        )

    assert type(raised.value) is smoke.SmokeError
    assert str(raised.value) == "Daytona smoke command response is invalid"
    assert supplied not in repr(raised.value)
    assert client.deleted

    monkeypatch.setattr(
        smoke, "run_real_smoke",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(raised.value),
    )
    assert smoke.main(["--real-smoke"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Daytona smoke command response is invalid\n"


def test_unconfirmed_deletion_suppresses_remote_command_diagnostics():
    client = _Client(absent=False)
    client.sandbox.process.exec = lambda *args, **kwargs: _Response(
        "opaque-host-key-sentinel", 9, "Bearer provider-secret"
    )
    with pytest.raises(smoke.SmokeError) as raised:
        smoke.run_real_smoke(
            ROOT,
            env={"VERIFY_DAYTONA": "1", "ALLOW_DAYTONA_MUTATION": "1", "DAYTONA_API_KEY": "opaque-host-key-sentinel"},
            client_factory=lambda *_: client,
        )
    assert type(raised.value) is smoke.SmokeError
    assert str(raised.value) == "Daytona sandbox deletion was not confirmed"
    assert "sentinel" not in repr(raised.value) and "provider-secret" not in repr(raised.value)


def test_cli_command_failure_emits_canonical_utf8_json_bytes(monkeypatch, capfdbinary):
    command_result = {
        "stage": "worker-import", "exitCode": 9,
        "stdout": "[REDACTED]", "stderr": "ImportError: bibliothèque introuvable ⚽",
    }
    monkeypatch.setattr(
        smoke, "run_real_smoke",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(smoke.SmokeCommandError(command_result)),
    )
    assert smoke.main(["--real-smoke"]) == 2
    captured = capfdbinary.readouterr()
    expected = {
        "mode": "real-smoke", "status": "failed",
        "error": "Daytona smoke command failed", "commandResult": command_result,
    }
    assert captured.out == smoke.canonical_json_bytes(expected)
    assert "bibliothèque introuvable ⚽".encode() in captured.out
    assert b"\\u" not in captured.out
    assert captured.err == b"Daytona smoke command failed\n"
    assert b"Traceback" not in captured.err


def test_unconfirmed_deletion_fails_without_final_report():
    client = _Client(absent=False)
    with pytest.raises(smoke.SmokeError, match="deletion"):
        smoke.run_real_smoke(ROOT, env={"VERIFY_DAYTONA": "1", "ALLOW_DAYTONA_MUTATION": "1", "DAYTONA_API_KEY": "secret"}, client_factory=lambda *_: client)


def test_default_cli_mode_is_dry_run():
    args = smoke._parser().parse_args([])
    assert not args.real_smoke


def test_create_is_not_retried_and_does_not_attempt_delete_without_a_sandbox():
    class FailingClient(_Client):
        def create(self, spec, timeout):
            self.created.append((spec, timeout))
            raise RuntimeError("capacity")
    client = FailingClient()
    with pytest.raises(smoke.SmokeError):
        smoke.run_real_smoke(ROOT, env={"VERIFY_DAYTONA": "1", "ALLOW_DAYTONA_MUTATION": "1", "DAYTONA_API_KEY": "secret"}, client_factory=lambda *_: client)
    assert len(client.created) == 1
    assert client.deleted == []


def test_unreturned_sdk_sandbox_is_recovered_by_smoke_outer_cleanup():
    class UnreturnedClient(_Client):
        def create(self, spec, timeout):
            self.created.append((spec, timeout))
            raise smoke._UnreturnedSandboxCleanupError(self.sandbox)
        def delete(self, sandbox, timeout, wait):
            self.deleted.append((sandbox.id, timeout, wait))
            raise RuntimeError("provider-secret")

    client = UnreturnedClient(absent=False)
    with pytest.raises(smoke.SmokeError) as raised:
        smoke.run_real_smoke(
            ROOT,
            env={"VERIFY_DAYTONA": "1", "ALLOW_DAYTONA_MUTATION": "1",
                 "DAYTONA_API_KEY": "test-key"},
            client_factory=lambda *_: client,
        )

    assert str(raised.value) == "Daytona sandbox deletion was not confirmed"
    assert "secret" not in str(raised.value)
    assert client.deleted == [("sandbox-1", 120, True)] * 3


def test_bad_completion_is_rejected_and_sandbox_is_deleted():
    client = _Client()
    original = client.sandbox.process.exec
    def corrupt_completion(command, **kwargs):
        response = original(command, **kwargs)
        if command == smoke.SMOKE_COMMAND:
            client.sandbox.fs.files[smoke.COMPLETION_PATH] = b'{}\n'
        return response
    client.sandbox.process.exec = corrupt_completion
    with pytest.raises(smoke.SmokeError, match="completion"):
        smoke.run_real_smoke(ROOT, env={"VERIFY_DAYTONA": "1", "ALLOW_DAYTONA_MUTATION": "1", "DAYTONA_API_KEY": "secret"}, client_factory=lambda *_: client)
    assert client.deleted


def test_oversized_download_is_rejected_and_sandbox_is_deleted():
    client = _Client()
    client.sandbox.fs.download_file_stream = lambda *_args, **_kwargs: iter([b"x" * (smoke.MAX_SMOKE_OUTPUT_BYTES + 1)])
    with pytest.raises(smoke.SmokeError, match="bounded"):
        smoke.run_real_smoke(ROOT, env={"VERIFY_DAYTONA": "1", "ALLOW_DAYTONA_MUTATION": "1", "DAYTONA_API_KEY": "secret"}, client_factory=lambda *_: client)
    assert client.deleted


def test_exact_committed_lock_is_required(tmp_path):
    worker = tmp_path / "backend/daytona_worker"
    worker.mkdir(parents=True)
    fixture = tmp_path / "backend/tests/fixtures/daytona"
    fixture.mkdir(parents=True)
    (tmp_path / "backend/requirements-runtime.txt").write_text("daytona==0.207.0\n")
    (fixture / "job-request.json").write_bytes((ROOT / "backend/tests/fixtures/daytona/job-request.json").read_bytes())
    (worker / "Dockerfile").write_text(smoke.expected_dockerfile())
    (worker / "requirements.txt").write_text((ROOT / "backend/daytona_worker/requirements.txt").read_text())
    lock = worker / "requirements.lock"
    lock.write_text((ROOT / "backend/daytona_worker/requirements.lock").read_text().replace("9e35d3e0", "0e35d3e0"))
    with pytest.raises(smoke.SmokeError, match="exact lock"):
        smoke.validate_worker_environment(tmp_path)


def test_duplicate_or_mismatched_runtime_sdk_pin_is_rejected(tmp_path):
    worker = tmp_path / "backend/daytona_worker"
    worker.mkdir(parents=True)
    fixture = tmp_path / "backend/tests/fixtures/daytona"
    fixture.mkdir(parents=True)
    (worker / "Dockerfile").write_text(smoke.expected_dockerfile())
    (worker / "requirements.txt").write_text((ROOT / "backend/daytona_worker/requirements.txt").read_text())
    (worker / "requirements.lock").write_text((ROOT / "backend/daytona_worker/requirements.lock").read_text())
    (fixture / "job-request.json").write_bytes((ROOT / "backend/tests/fixtures/daytona/job-request.json").read_bytes())
    runtime = tmp_path / "backend/requirements-runtime.txt"
    runtime.write_text("daytona==0.207.0\ndaytona==999.0.0\n")
    with pytest.raises(smoke.SmokeError, match="SDK"):
        smoke.validate_worker_environment(tmp_path)


def test_dry_run_requires_the_exact_canonical_bounded_fixture(tmp_path):
    worker = tmp_path / "backend/daytona_worker"
    worker.mkdir(parents=True)
    fixture = tmp_path / "backend/tests/fixtures/daytona"
    fixture.mkdir(parents=True)
    (worker / "Dockerfile").write_text(smoke.expected_dockerfile())
    (worker / "requirements.txt").write_text((ROOT / "backend/daytona_worker/requirements.txt").read_text())
    (worker / "requirements.lock").write_text((ROOT / "backend/daytona_worker/requirements.lock").read_text())
    (tmp_path / "backend/requirements-runtime.txt").write_text("daytona==0.207.0\n")
    (fixture / "job-request.json").write_text('{"config":{},"inputVideoPath":"input.mp4","jobId":"other","matchId":"smoke-match","receiptPath":"receipt.json","schemaVersion":1}\n')
    with pytest.raises(smoke.SmokeError, match="fixture"):
        smoke.validate_worker_environment(tmp_path)


def test_fake_surface_has_no_preview_snapshot_volume_registry_or_runpod_calls():
    client = _Client()
    smoke.run_real_smoke(ROOT, env={"VERIFY_DAYTONA": "1", "ALLOW_DAYTONA_MUTATION": "1", "DAYTONA_API_KEY": "secret"}, client_factory=lambda *_: client)
    forbidden = {"preview", "snapshot", "volume", "registry", "runpod"}
    assert not forbidden.intersection(vars(client))


def test_secret_bearing_command_output_is_rejected_after_cleanup():
    client = _Client()
    original = client.sandbox.process.exec
    def secret_output(command, **kwargs):
        response = original(command, **kwargs)
        if command == smoke.WORKER_IMPORT_COMMAND:
            response.result = "api_key=should-never-be-evidence"
        return response
    client.sandbox.process.exec = secret_output
    with pytest.raises(smoke.SmokeError, match="report"):
        smoke.run_real_smoke(ROOT, env={"VERIFY_DAYTONA": "1", "ALLOW_DAYTONA_MUTATION": "1", "DAYTONA_API_KEY": "secret"}, client_factory=lambda *_: client)
    assert client.deleted


def test_absence_check_trusts_only_typed_adapter_signal_and_passes_timeout():
    class RawNameCollision(Exception): pass
    RawNameCollision.__name__ = "DaytonaNotFoundError"
    client = _Client()
    calls = []
    def get(sandbox_id, timeout):
        calls.append((sandbox_id, timeout))
        raise RawNameCollision()
    client.get = get
    with pytest.raises(smoke.SmokeError, match="deletion"):
        smoke.run_real_smoke(ROOT, env={"VERIFY_DAYTONA": "1", "ALLOW_DAYTONA_MUTATION": "1", "DAYTONA_API_KEY": "secret"}, client_factory=lambda *_: client)
    assert calls == [("sandbox-1", 120)]


def test_production_factory_builds_committed_dockerfile_with_bounded_context(monkeypatch):
    calls = []
    image = object()
    class Image:
        @staticmethod
        def base(base):
            calls.append(("base", base))
            return Image()
        def dockerfile_commands(self, commands, context_dir=None):
            calls.append(("commands", commands, context_dir))
            return image
    class Adapter:
        def __init__(self, raw, sdk, *, image=None, image_factory=None):
            assert image is None
            with image_factory() as built:
                calls.append(("built", built))
    sdk = type("SDK", (), {"Image": Image, "Daytona": lambda config: ("raw", config),
                            "DaytonaConfig": lambda **values: values})
    monkeypatch.setitem(__import__("sys").modules, "daytona", sdk)
    monkeypatch.setattr(__import__("backend.app.daytona", fromlist=["_SdkClient"]), "_SdkClient", Adapter)
    digests = []
    smoke._production_client_factory("secret", "us", ROOT, digests.append)
    assert calls[0] == ("base", smoke.IMAGE)
    assert calls[1][0] == "commands"
    assert calls[1][1] == smoke.expected_dockerfile().splitlines()[1:]
    context = Path(calls[1][2])
    assert calls[2] == ("built", image)
    assert not context.exists()
    assert "backend/tests" not in {path.as_posix() for path in context.rglob("*")}
    assert len(digests) == 1


def test_worker_image_digest_describes_exact_built_context_after_source_mutation(tmp_path, monkeypatch):
    for relative in smoke.WORKER_CONTEXT_MEMBERS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.encode())
    (tmp_path / "backend/daytona_worker/Dockerfile").write_text("FROM sealed\nCOPY backend /workspace/backend\n")
    observed = []
    class Image:
        @staticmethod
        def base(_): return Image()
        def dockerfile_commands(self, commands, context_dir=None):
            context = Path(context_dir)
            observed.append(smoke.worker_context_sha256(context))
            return object()
    digests = []
    factory = __import__("backend.app.daytona_worker_image", fromlist=["worker_image_factory"]).worker_image_factory(
        type("SDK", (), {"Image": Image}), tmp_path, digests.append
    )
    with factory():
        (tmp_path / smoke.WORKER_CONTEXT_MEMBERS[0]).write_bytes(b"mutated after seal")
    assert digests == observed


def test_worker_image_digest_is_reported_only_after_unchanged_context_use(tmp_path):
    for relative in smoke.WORKER_CONTEXT_MEMBERS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.encode())
    (tmp_path / "backend/daytona_worker/Dockerfile").write_text(
        "FROM sealed\nCOPY backend /workspace/backend\n"
    )
    context_paths = []
    class Image:
        @staticmethod
        def base(_): return Image()
        def dockerfile_commands(self, commands, context_dir=None):
            context_paths.append(Path(context_dir))
            return object()
    digests = []
    factory = __import__(
        "backend.app.daytona_worker_image", fromlist=["worker_image_factory"]
    ).worker_image_factory(type("SDK", (), {"Image": Image}), tmp_path, digests.append)

    with pytest.raises(smoke.WorkerImageError, match="changed"):
        with factory():
            assert digests == []
            (context_paths[0] / smoke.WORKER_CONTEXT_MEMBERS[0]).write_bytes(b"tampered")
    assert digests == []


def test_worker_context_is_private_bounded_exact_and_cleaned():
    with smoke._worker_context(ROOT) as context:
        assert context.stat().st_mode & 0o777 == 0o700
        files = {path.relative_to(context).as_posix() for path in context.rglob("*") if path.is_file()}
        assert files == set(smoke.WORKER_CONTEXT_MEMBERS)
        assert not any("__pycache__" in item or "tests/" in item or "storage/" in item for item in files)
    assert not context.exists()


def test_worker_context_rejects_symlink_and_oversize_and_cleans(tmp_path, monkeypatch):
    for relative in smoke.WORKER_CONTEXT_MEMBERS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    victim = tmp_path / smoke.WORKER_CONTEXT_MEMBERS[0]
    victim.unlink()
    victim.symlink_to(tmp_path / smoke.WORKER_CONTEXT_MEMBERS[1])
    with pytest.raises(smoke.WorkerImageError, match="context"):
        with smoke._worker_context(tmp_path): pass
    assert not list(Path("/tmp").glob("daytona-worker-context-*"))
    victim.unlink(); victim.write_bytes(b"x" * (smoke.MAX_CONTEXT_MEMBER_BYTES + 1))
    with pytest.raises(smoke.WorkerImageError, match="bounded"):
        with smoke._worker_context(tmp_path): pass
    assert not list(Path("/tmp").glob("daytona-worker-context-*"))


def test_context_copy_rejects_source_identity_change(tmp_path, monkeypatch):
    from types import SimpleNamespace
    root = tmp_path / "source"; context = tmp_path / "context"
    root.mkdir(); context.mkdir()
    source = root / "member.py"; source.write_bytes(b"safe")
    real_stat = Path.stat
    calls = 0
    def changed(path, *args, **kwargs):
        nonlocal calls
        value = real_stat(path, *args, **kwargs)
        if path == source and kwargs.get("follow_symlinks") is False:
            calls += 1
            if calls == 2:
                values = {name: getattr(value, name) for name in (
                    "st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns"
                )}
                values["st_mtime_ns"] += 1
                return SimpleNamespace(**values)
        return value
    monkeypatch.setattr(Path, "stat", changed)
    with pytest.raises(smoke.WorkerImageError, match="changed"):
        smoke._copy_context_member(root, context, "member.py", 0)
