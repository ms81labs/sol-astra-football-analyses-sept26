"""Validate, or explicitly run, one bounded Daytona GPU smoke."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import re
from typing import Callable, Mapping, Sequence

from backend.app.daytona import (
    DaytonaConfirmedAbsent,
    DaytonaSandboxSpec,
    _UnreturnedSandboxCleanupError,
)
from backend.app.daytona_worker_image import (
    MAX_CONTEXT_MEMBER_BYTES as MAX_CONTEXT_MEMBER_BYTES,
    WORKER_CONTEXT_MEMBERS as WORKER_CONTEXT_MEMBERS,
    WorkerImageError as WorkerImageError,
    _copy_context_member as _copy_context_member,
    worker_context,
    worker_context_sha256 as worker_context_sha256,
    worker_image_factory,
)

_worker_context = worker_context
from backend.app.release_manifest import ReleaseManifest
from backend.app.remote_contracts import (
    JobRequest, canonical_json_bytes, redact_remote_diagnostics,
)
from backend.release.daytona_policy import DaytonaPolicy, load_daytona_policy
from backend.release.evidence import PreflightError, RemoteExecution, _timestamp as _parse_timestamp


IMAGE = "docker.io/pytorch/pytorch@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385"
SMOKE_COMMAND = (
    "python -c \"import hashlib,json; from pathlib import Path; "
    "p=json.loads(Path('/home/daytona/smoke/job-request.json').read_text()); "
    "r={'jobId':p['jobId'],'matchId':p['matchId'],'status':'passed'}; "
    "b=(json.dumps(r,sort_keys=True,separators=(',',':'))+'\\\\n').encode(); "
    "Path('/home/daytona/smoke/result.json').write_bytes(b); "
    "c={'jobId':p['jobId'],'matchId':p['matchId'],'resultPath':'/home/daytona/smoke/result.json','resultSizeBytes':len(b),'resultSha256':hashlib.sha256(b).hexdigest()}; "
    "Path('/home/daytona/smoke/completion.json').write_text(json.dumps(c,sort_keys=True,separators=(',',':'))+'\\\\n')\""
)
RESULT_PATH = "/home/daytona/smoke/result.json"
COMPLETION_PATH = "/home/daytona/smoke/completion.json"
MAX_SMOKE_OUTPUT_BYTES = 64 * 1024
WORKER_IMPORT_COMMAND = (
    "python -c \"import boto3,cv2,lap,numpy,pandas,pydantic,torch,ultralytics; "
    "from ultralytics.trackers.utils import matching; "
    "import backend.app.processor,backend.app.proof_runtime; "
    "assert matching.lap is lap; "
    "assert torch.cuda.is_available(); "
    "value=torch.ones(1,device='cuda'); assert float(value.item())==1.0\""
)
_DIRECT_REQUIREMENTS_SHA256 = "d12d96be5d52d6ec1531c27cfe15f43620442ceee4140315a6d8fe380eeaad3d"
_LOCKED_REQUIREMENTS_SHA256 = "2fdb83df878b63913d5639a021d563144374eb2c8b976b5a74661df2891692c2"
_LOCK_HASH = re.compile(r"--hash=sha256:[0-9a-f]{64}(?: |$)")
_FIXTURE = {"schemaVersion": 1, "jobId": "smoke-job", "matchId": "smoke-match",
    "receiptPath": "receipt.json", "inputVideoPath": "input.mp4", "config": {}}


class SmokeError(RuntimeError):
    pass


MAX_FAILURE_DIAGNOSTIC_CHARS = 2048


class SmokeCommandError(SmokeError):
    def __init__(self, command_result: dict[str, object]):
        super().__init__("Daytona smoke command failed")
        self.command_result = command_result


def expected_dockerfile() -> str:
    return (
        f"FROM {IMAGE}\n"
        "WORKDIR /workspace\n"
        "RUN apt-get update \\\n"
        " && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \\\n"
        "      libgl1 libglib2.0-0 libxcb1 \\\n"
        " && rm -rf /var/lib/apt/lists/*\n"
        "ENV QT_QPA_PLATFORM=offscreen\n"
        "ENV YOLO_AUTOINSTALL=false\n"
        "ENV PYTHONPATH=/workspace\n"
        "COPY backend/daytona_worker/requirements.lock /tmp/requirements.lock\n"
        "RUN python -m pip uninstall --yes torchaudio \\\n"
        " && python -m pip install --require-hashes --no-deps -r /tmp/requirements.lock \\\n"
        " && python -m pip check\n"
        "COPY lap.py /workspace/lap.py\n"
        "COPY backend /workspace/backend\n"
    )


def _requirements(path: Path, *, expected_sha256: str) -> str:
    try:
        value = path.read_text(encoding="utf-8")
    except OSError:
        raise SmokeError("worker requirements are unavailable") from None
    if hashlib.sha256(value.encode()).hexdigest() != expected_sha256:
        raise SmokeError("worker requirements do not match the exact lock")
    return value


def validate_worker_environment(repo_root: Path) -> DaytonaPolicy:
    policy = load_daytona_policy()
    worker = repo_root / "backend/daytona_worker"
    try:
        dockerfile = (worker / "Dockerfile").read_text(encoding="utf-8")
    except OSError:
        raise SmokeError("worker Dockerfile is unavailable") from None
    if dockerfile != expected_dockerfile() or policy.image != IMAGE:
        raise SmokeError("worker Dockerfile does not match immutable policy")
    direct = _requirements(worker / "requirements.txt", expected_sha256=_DIRECT_REQUIREMENTS_SHA256)
    locked = _requirements(worker / "requirements.lock", expected_sha256=_LOCKED_REQUIREMENTS_SHA256)
    pins = {line for line in direct.splitlines() if line and not line.startswith("#")}
    lock_lines = locked.splitlines()
    locked_pins = {line.split(" --hash=", 1)[0] for line in lock_lines}
    if not pins.issubset(locked_pins) or any(_LOCK_HASH.search(line) is None for line in lock_lines):
        raise SmokeError("worker requirements do not match the exact lock")
    try:
        fixture = (repo_root / "backend/tests/fixtures/daytona/job-request.json").read_bytes()
        request = JobRequest.from_mapping(json.loads(fixture))
    except Exception:
        raise SmokeError("smoke fixture contract is invalid") from None
    if request.to_mapping() != _FIXTURE or fixture != canonical_json_bytes(_FIXTURE):
        raise SmokeError("smoke fixture is not the exact canonical bounded fixture")
    try:
        runtime_path = repo_root / "backend/requirements/api.in"
        if not runtime_path.exists():
            runtime_path = repo_root / "backend/requirements-runtime.txt"
        runtime = [line for line in runtime_path.read_text(encoding="utf-8").splitlines() if line.startswith("daytona==")]
    except OSError:
        raise SmokeError("Daytona SDK policy mismatch") from None
    if runtime != [f"daytona=={policy.sdk_version}"]:
        raise SmokeError("Daytona SDK policy mismatch")
    return policy


def validate_mutation_authorization(env: Mapping[str, str]) -> str:
    if env.get("VERIFY_DAYTONA") != "1" or env.get("ALLOW_DAYTONA_MUTATION") != "1":
        raise SmokeError("Daytona mutation authorization is required")
    key = env.get("DAYTONA_API_KEY", "")
    if not key.strip() or len(key) > 4096 or "\0" in key:
        raise SmokeError("Daytona credentials are unavailable")
    return key


def run_dry_run(repo_root: Path) -> dict[str, object]:
    policy = validate_worker_environment(repo_root)
    return {"mode": "dry-run", "sdkVersion": policy.sdk_version, "image": policy.image, "target": policy.target, "gpuTypes": list(policy.gpu_types)}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _spec(policy: DaytonaPolicy) -> DaytonaSandboxSpec:
    return DaytonaSandboxSpec(policy.image, policy.public, policy.ephemeral, policy.spot, policy.ttl_minutes, policy.network_block_all, (), policy.cpu, policy.memory_gib, policy.disk_gib, policy.gpu, policy.gpu_types)


def _production_client_factory(api_key: str, target: str, repo_root: Path | None = None,
                               digest_callback: Callable[[str], None] | None = None):
    module = importlib.import_module("backend.app.daytona")
    root = repo_root or Path(__file__).resolve().parents[2]
    sdk = importlib.import_module("daytona")
    return module._production_client_factory(
        api_key, target, image_factory=worker_image_factory(sdk, root, digest_callback)
    )


def _release_binding(repo_root: Path) -> tuple[dict[str, str], datetime]:
    from backend.release.preflight import (
        _json_bytes_mapping,
        validate_git_source,
        validate_verification_binding,
    )
    from backend.scripts.write_verification_evidence import _load_verifier_receipt, _manifest_bytes

    try:
        now = datetime.now(timezone.utc)
        receipt = _load_verifier_receipt(repo_root, now)
        manifest_bytes = _manifest_bytes(repo_root)
        manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
        if manifest_sha != receipt["manifestSha256"]:
            raise SmokeError("release manifest does not match verifier receipt")
        manifest = ReleaseManifest.from_mapping(
            _json_bytes_mapping(manifest_bytes, "release manifest")
        )
        validate_git_source(
            repo_root,
            manifest.source_commit,
            required_tracked_paths=("backend/release/v7.3.json",),
        )
        verification_commit = str(receipt["repositoryCommit"])
        validate_verification_binding(
            repo_root, verification_commit, "backend/release/v7.3.json", manifest_sha
        )
        created_at = _parse_timestamp(str(receipt["createdAt"]), "receipt createdAt")
    except SmokeError:
        raise
    except Exception:
        raise SmokeError("release verification binding is invalid") from None
    return ({"sourceCommit": manifest.source_commit, "verificationCommit": verification_commit,
             "manifestSha256": manifest_sha}, created_at)


def _without_api_key(value: object, api_key: str) -> object:
    if type(value) is not str:
        return "[UNAVAILABLE]"
    return str.replace(value, api_key, "[REDACTED]")


def _failed_command_result(response, label: str, exit_code: int,
                           api_key: str) -> dict[str, object]:
    result = redact_remote_diagnostics(
        {
            "stdout": _without_api_key(getattr(response, "result", ""), api_key),
            "stderr": _without_api_key(getattr(response, "stderr", ""), api_key),
        },
        max_output_chars=MAX_FAILURE_DIAGNOSTIC_CHARS,
        max_depth=1,
        max_items=2,
    )
    if (type(result) is not dict or type(result.get("stdout")) is not str
            or type(result.get("stderr")) is not str):
        stdout = stderr = "[REDACTED]"
    else:
        stdout, stderr = result["stdout"], result["stderr"]
    return {"stage": label, "exitCode": exit_code, "stdout": stdout, "stderr": stderr}


def _exec(sandbox, command: str, label: str, timeout: int, *,
          api_key: str) -> tuple[str, dict[str, object]]:
    response = sandbox.process.exec(command, cwd="/workspace", env={}, timeout=timeout)
    exit_code = getattr(response, "exit_code", None)
    if type(exit_code) is not int or not 0 <= exit_code <= 255:
        raise SmokeError("Daytona smoke command response is invalid")
    if exit_code != 0:
        raise SmokeCommandError(_failed_command_result(response, label, exit_code, api_key))
    stdout = getattr(response, "result", "")
    stderr = getattr(response, "stderr", "")
    if (type(stdout) is not str or type(stderr) is not str or len(stdout) > 4096
            or len(stderr) > 4096 or "\0" in stdout or "\0" in stderr):
        raise SmokeError("Daytona smoke command output is not bounded")
    stdout, stderr = ("" if api_key in stdout else stdout), ("" if api_key in stderr else stderr)
    return stdout, {"command": label, "exitCode": exit_code, "stdout": stdout, "stderr": stderr}


def _download(sandbox, path: str, timeout: int) -> bytes:
    payload = bytearray()
    try:
        for chunk in sandbox.fs.download_file_stream(path, timeout=timeout):
            if type(chunk) is not bytes or len(payload) + len(chunk) > MAX_SMOKE_OUTPUT_BYTES:
                raise SmokeError("Daytona smoke download is not bounded")
            payload.extend(chunk)
    except SmokeError:
        raise
    except Exception:
        raise SmokeError("Daytona smoke download failed") from None
    if not payload:
        raise SmokeError("Daytona smoke download is empty")
    return bytes(payload)


def _confirmed_absent(client, sandbox_id: str, timeout: int) -> bool:
    try:
        client.get(sandbox_id, timeout)
    except DaytonaConfirmedAbsent:
        return True
    except Exception:
        return False
    return False


def run_real_smoke(repo_root: Path, *, env: Mapping[str, str] = os.environ,
                   client_factory: Callable[[str, str], object] = _production_client_factory) -> dict[str, object]:
    key = validate_mutation_authorization(env)
    policy = validate_worker_environment(repo_root)
    try:
        release_binding, receipt_created_at = _release_binding(repo_root)
    except SmokeError:
        raise
    except Exception:
        raise SmokeError("release verification binding is invalid") from None
    context_digests: list[str] = []
    try:
        client = (
            client_factory(key, policy.target, repo_root, context_digests.append)
            if client_factory is _production_client_factory
            else client_factory(key, policy.target)
        )
    except Exception:
        raise SmokeError("Daytona client construction failed") from None
    sandbox = None
    cleanup_attempts = 0
    created = started = completed = deleted = None
    pending: BaseException | None = None
    report: dict[str, object] | None = None
    try:
        created = _timestamp()
        if _parse_timestamp(created, "remote createdAt") < receipt_created_at:
            raise SmokeError("Daytona smoke predates verifier receipt")
        sandbox = client.create(_spec(policy), timeout=policy.create_timeout_seconds)
        if client_factory is not _production_client_factory:
            context_digests.append(getattr(client, "worker_context_sha256", ""))
        if len(context_digests) != 1 or re.fullmatch(r"[0-9a-f]{64}", context_digests[0]) is None:
            raise SmokeError("Daytona worker context identity is unavailable")
        started = _timestamp()
        observed_raw, gpu_command = _exec(sandbox, "nvidia-smi --query-gpu=name --format=csv,noheader", "nvidia-smi", policy.execution_timeout_seconds, api_key=key)
        observed = next((gpu for gpu in policy.gpu_types if gpu.replace("-", " ") in observed_raw.replace("NVIDIA ", "").replace("-", " ")), None)
        if observed is None:
            raise SmokeError("Daytona smoke observed an unexpected GPU")
        _exec(sandbox, "mkdir -p /home/daytona/smoke", "smoke-directory", policy.execution_timeout_seconds, api_key=key)
        _, import_command = _exec(sandbox, WORKER_IMPORT_COMMAND, "worker-import", policy.execution_timeout_seconds, api_key=key)
        fixture = (repo_root / "backend/tests/fixtures/daytona/job-request.json").read_bytes()
        if not fixture or len(fixture) > 16_384:
            raise SmokeError("Daytona smoke fixture is not bounded")
        digest = hashlib.sha256(fixture).hexdigest()
        sandbox.fs.upload_file_stream(io.BytesIO(fixture), "/home/daytona/smoke/job-request.json", timeout=policy.transfer_timeout_seconds)
        _, fixture_command = _exec(sandbox, SMOKE_COMMAND, "bounded-fixture", policy.execution_timeout_seconds, api_key=key)
        payload = _download(sandbox, RESULT_PATH, policy.transfer_timeout_seconds)
        completion_payload = _download(sandbox, COMPLETION_PATH, policy.transfer_timeout_seconds)
        try:
            result = json.loads(payload)
            completion = json.loads(completion_payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise SmokeError("Daytona smoke result or completion is invalid") from None
        if result != {"jobId": "smoke-job", "matchId": "smoke-match", "status": "passed"} or payload != canonical_json_bytes(result):
            raise SmokeError("Daytona smoke result validation failed")
        expected_completion = {"jobId": "smoke-job", "matchId": "smoke-match", "resultPath": RESULT_PATH,
            "resultSizeBytes": len(payload), "resultSha256": hashlib.sha256(payload).hexdigest()}
        if completion != expected_completion or completion_payload != canonical_json_bytes(completion):
            raise SmokeError("Daytona smoke completion validation failed")
        completed = _timestamp()
        report = {**release_binding, "workerContextSha256": context_digests[0],
            "sdkVersion": policy.sdk_version, "imageDigest": policy.image, "requestedTarget": policy.target,
            "requestedGpuOrder": list(policy.gpu_types), "observedGpu": observed, "sandboxId": sandbox.id,
            "createdAt": created, "startedAt": started, "completedAt": completed,
            "commandResults": [gpu_command, import_command, fixture_command],
            "uploads": [{"name": "job-request.json", "sizeBytes": len(fixture), "sha256": digest}],
            "downloads": [
                {"name": "result.json", "sizeBytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()},
                {"name": "completion.json", "sizeBytes": len(completion_payload), "sha256": hashlib.sha256(completion_payload).hexdigest()},
            ],
            "runpodMutationOccurred": False, "registryMutationOccurred": False}
    except _UnreturnedSandboxCleanupError as exc:
        sandbox = exc.sandbox
        pending = SmokeError("Daytona sandbox creation cleanup was not confirmed")
    except BaseException as exc:
        pending = exc
    finally:
        if sandbox is not None:
            for _ in range(policy.cleanup_attempts):
                cleanup_attempts += 1
                try:
                    client.delete(sandbox, timeout=policy.delete_timeout_seconds, wait=True)
                    break
                except DaytonaConfirmedAbsent:
                    break
                except Exception:
                    continue
            if not _confirmed_absent(client, sandbox.id, policy.delete_timeout_seconds):
                raise SmokeError("Daytona sandbox deletion was not confirmed") from None
            deleted = _timestamp()
    if pending is not None:
        if isinstance(pending, SmokeError): raise pending
        raise SmokeError("Daytona smoke failed") from None
    if report is None:
        raise SmokeError("Daytona smoke produced no validated result")
    report.update({"deletedAt": deleted, "cleanupAttempts": cleanup_attempts, "deletionConfirmed": True})
    try:
        RemoteExecution.from_mapping(report)
    except PreflightError:
        raise SmokeError("Daytona smoke report validation failed") from None
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--real-smoke", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    try:
        report = run_real_smoke(root) if args.real_smoke else run_dry_run(root)
    except SmokeCommandError as exc:
        error = "Daytona smoke command failed"
        os.sys.stdout.buffer.write(canonical_json_bytes({
            "mode": "real-smoke", "status": "failed", "error": error,
            "commandResult": exc.command_result,
        }))
        print(error, file=os.sys.stderr)
        return 2
    except SmokeError as exc:
        print(str(exc), file=os.sys.stderr)
        return 2
    os.sys.stdout.buffer.write(canonical_json_bytes(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
