from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from backend.release.evidence import (
    REMOTE_GATE_NAME, PreflightError, REQUIRED_GATE_COMMANDS, VerificationEvidence,
    VerificationGate, validate_evidence_freshness, validate_evidence_phase,
    validate_evidence_validity_window,
)

EXPECTED_GATE_COMMANDS = (
    ("backend", "python3 -m pytest -q backend/tests"),
    ("sidecar", "python3 -m pytest -q research-addon/tests"),
    ("frontend-tests", "npm --prefix frontend test -- --run"),
    ("lint", "npm --prefix frontend run lint"),
    ("typecheck-app", "cd frontend && npx tsc -p tsconfig.app.json --noEmit --incremental false"),
    ("typecheck-node", "cd frontend && npx tsc -p tsconfig.node.json --noEmit --incremental false"),
    ("build", "npm --prefix frontend run build"),
    ("backend-startup", "python3 -c 'from backend.app.main import app'"),
    ("manifest", "python3 -m pytest -q backend/tests/test_release_manifest.py backend/tests/test_write_release_manifest.py"),
    ("runtime-options", "python3 -m pytest -q backend/tests/test_runtime_options.py"),
    ("preflight-negatives", "python3 -m pytest -q backend/tests/test_release_preflight.py -k reject"),
    ("prod-audit", "npm --prefix frontend audit --omit=dev --audit-level=high"),
    ("daytona-gpu-smoke", "python3 -m backend.scripts.run_daytona_gpu_smoke --real-smoke"),
)


def _remote_execution() -> dict[str, object]:
    return {
        "sourceCommit": "a" * 40, "verificationCommit": "c" * 40,
        "manifestSha256": "b" * 64, "workerContextSha256": "e" * 64,
        "sdkVersion": "0.207.0", "imageDigest": "docker.io/pytorch/pytorch@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385",
        "requestedTarget": "us", "requestedGpuOrder": ["RTX-PRO-6000", "H100"],
        "observedGpu": "RTX-PRO-6000", "sandboxId": "sandbox-123",
        "createdAt": "2026-08-22T12:30:01Z", "startedAt": "2026-08-22T12:30:02Z",
        "completedAt": "2026-08-22T12:30:03Z", "deletedAt": "2026-08-22T12:30:04Z",
        "commandResults": [{"command": "nvidia-smi", "exitCode": 0, "stdout": "GPU ready", "stderr": ""}],
        "uploads": [{"name": "context", "sha256": "c" * 64, "sizeBytes": 12}],
        "downloads": [{"name": "result", "sha256": "d" * 64, "sizeBytes": 34}],
        "cleanupAttempts": 1, "deletionConfirmed": True,
        "runpodMutationOccurred": False, "registryMutationOccurred": False,
    }


def _evidence(*, phase: str = "pre_cloud") -> dict[str, object]:
    pre_cloud = phase == "pre_cloud"
    return {
        "schemaVersion": 2, "phase": phase, "sourceCommit": "a" * 40,
        "verificationCommit": "c" * 40, "manifestSha256": "b" * 64,
        "createdAt": "2026-08-22T13:00:00Z",
        "toolVersions": {"pytest": "8.4.1", "python": "3.11.9"},
        "gates": [{"name": name, "command": command,
                   "status": "pending" if pre_cloud and name == REMOTE_GATE_NAME else "passed",
                   "completedAt": None if pre_cloud and name == REMOTE_GATE_NAME else (
                       "2026-08-22T12:30:04Z" if name == REMOTE_GATE_NAME else "2026-08-22T12:20:00Z"
                   ),
                   "logSha256": None if pre_cloud and name == REMOTE_GATE_NAME else "d" * 64}
                  for name, command in REQUIRED_GATE_COMMANDS.items()],
        "overallPassed": not pre_cloud,
        "remoteExecution": None if pre_cloud else _remote_execution(),
    }


def _gate(payload: dict[str, object], name: str) -> dict[str, object]:
    return next(gate for gate in payload["gates"] if gate["name"] == name)  # type: ignore[union-attr]


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def receipt_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"; root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "release-tests@example.invalid")
    _git(root, "config", "user.name", "Release Tests")
    from backend.app.daytona_worker_image import WORKER_CONTEXT_MEMBERS

    project = Path(__file__).parents[2]
    for relative in WORKER_CONTEXT_MEMBERS:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(project / relative, target)
    (root / ".gitignore").write_text(".verification/\n", encoding="utf-8")
    _git(root, "add", ".gitignore", *WORKER_CONTEXT_MEMBERS)
    _git(root, "commit", "-m", "metadata")
    logs = root / ".verification/logs"; logs.mkdir(parents=True)
    base = datetime(2026, 8, 22, 12, tzinfo=timezone.utc).timestamp()
    for index, name in enumerate(tuple(REQUIRED_GATE_COMMANDS)[:-1]):
        log = logs / f"{name}.log"
        log.write_bytes(b"" if name.startswith("typecheck") else f"{name} passed\n".encode())
        timestamp = base + index
        os.utime(log, (timestamp, timestamp))
    return root


def _record_receipt(root: Path) -> dict[str, object]:
    from backend.scripts.write_verification_evidence import record_verifier_success

    return record_verifier_success(
        root, now=datetime(2026, 8, 22, 12, 30, tzinfo=timezone.utc)
    )


def test_required_gate_commands_preserve_exact_current_contract() -> None:
    assert tuple(REQUIRED_GATE_COMMANDS.items()) == EXPECTED_GATE_COMMANDS


def test_evidence_types_are_owned_by_release_module() -> None:
    assert VerificationGate.__module__ == VerificationEvidence.__module__ == "backend.release.evidence"


def test_verification_evidence_parses_strict_contract() -> None:
    evidence = VerificationEvidence.from_mapping(_evidence())
    assert evidence.schema_version == 2 and evidence.phase == "pre_cloud"
    assert evidence.verification_commit == "c" * 40
    assert evidence.remote_execution is None
    assert tuple(gate.name for gate in evidence.gates) == tuple(REQUIRED_GATE_COMMANDS)


@pytest.mark.parametrize("field,bad", [
    ("sourceCommit", "f" * 40),
    ("verificationCommit", "f" * 40),
    ("manifestSha256", "f" * 64),
])
def test_final_remote_execution_must_bind_same_release(field: str, bad: str) -> None:
    payload = _evidence(phase="final")
    payload["remoteExecution"][field] = bad  # type: ignore[index]
    with pytest.raises(PreflightError, match=field):
        VerificationEvidence.from_mapping(payload)


@pytest.mark.parametrize("field,value", [
    ("sourceCommit", "A" * 40),
    ("verificationCommit", "a" * 39),
    ("manifestSha256", "B" * 64),
    ("workerContextSha256", "b" * 63),
])
def test_remote_release_binding_rejects_invalid_digests(field: str, value: object) -> None:
    payload = _evidence(phase="final")
    payload["remoteExecution"][field] = value  # type: ignore[index]
    with pytest.raises(PreflightError, match=field):
        VerificationEvidence.from_mapping(payload)


def test_verification_commit_and_gate_log_sha_round_trip() -> None:
    payload = _evidence()
    assert VerificationEvidence.from_mapping(payload).to_mapping() == payload


@pytest.mark.parametrize("value", [None, 7, "a" * 39, "a" * 41, "A" * 40])
def test_verification_commit_rejects_invalid_type_length_and_case(value: object) -> None:
    from jsonschema import Draft202012Validator

    payload = _evidence(); payload["verificationCommit"] = value
    schema = json.loads(
        (Path(__file__).parents[1] / "release/verification_schema.json").read_text()
    )
    with pytest.raises(PreflightError, match="verificationCommit"):
        VerificationEvidence.from_mapping(payload)
    assert list(Draft202012Validator(schema).iter_errors(payload))


@pytest.mark.parametrize("mutation", ["missing", "unknown"])
def test_verification_commit_rejects_missing_and_unknown_keys(mutation: str) -> None:
    from jsonschema import Draft202012Validator

    payload = _evidence()
    if mutation == "missing":
        del payload["verificationCommit"]
    else:
        payload["verification_commit"] = payload["verificationCommit"]
    schema = json.loads(
        (Path(__file__).parents[1] / "release/verification_schema.json").read_text()
    )
    with pytest.raises(PreflightError, match="verification evidence (missing|unknown) keys"):
        VerificationEvidence.from_mapping(payload)
    assert list(Draft202012Validator(schema).iter_errors(payload))


@pytest.mark.parametrize("status", ["passed", "failed"])
def test_gate_log_sha_accepts_digest_for_completed_statuses(status: str) -> None:
    payload = _evidence(); gate = _gate(payload, "backend")
    gate["status"] = status
    assert VerificationEvidence.from_mapping(payload).gates[0].log_sha256 == "d" * 64


@pytest.mark.parametrize("value", [None, 7, "d" * 63, "d" * 65, "D" * 64])
def test_gate_log_sha_rejects_invalid_completed_digest(value: object) -> None:
    from jsonschema import Draft202012Validator

    payload = _evidence(); _gate(payload, "backend")["logSha256"] = value
    schema = json.loads(
        (Path(__file__).parents[1] / "release/verification_schema.json").read_text()
    )
    with pytest.raises(PreflightError, match="logSha256"):
        VerificationEvidence.from_mapping(payload)
    assert list(Draft202012Validator(schema).iter_errors(payload))


@pytest.mark.parametrize("mutation", ["missing", "unknown"])
def test_gate_log_sha_rejects_missing_and_unknown_keys(mutation: str) -> None:
    from jsonschema import Draft202012Validator

    payload = _evidence(); gate = _gate(payload, "backend")
    if mutation == "missing":
        del gate["logSha256"]
    else:
        gate["log_sha256"] = gate["logSha256"]
    schema = json.loads(
        (Path(__file__).parents[1] / "release/verification_schema.json").read_text()
    )
    with pytest.raises(PreflightError, match="gate (missing|unknown) keys"):
        VerificationEvidence.from_mapping(payload)
    assert list(Draft202012Validator(schema).iter_errors(payload))


def test_gate_log_sha_must_be_null_only_while_pending() -> None:
    from jsonschema import Draft202012Validator

    payload = _evidence(); _gate(payload, REMOTE_GATE_NAME)["logSha256"] = "d" * 64
    schema = json.loads(
        (Path(__file__).parents[1] / "release/verification_schema.json").read_text()
    )
    with pytest.raises(PreflightError, match="pending gate logSha256 must be null"):
        VerificationEvidence.from_mapping(payload)
    assert list(Draft202012Validator(schema).iter_errors(payload))


@pytest.mark.parametrize("timestamp", ["2026-08-22T12:30:00+00:00", "2026-08-22 12:30:00Z", "2026-08-22T12:30Z", "2026-08-22T12:30:00.1234567890Z"])
def test_verification_evidence_rejects_noncanonical_timestamps(timestamp: str) -> None:
    payload = _evidence(); payload["createdAt"] = timestamp
    with pytest.raises(PreflightError, match="exact UTC RFC3339"): VerificationEvidence.from_mapping(payload)


def test_verification_evidence_rejects_duplicate_gate_names() -> None:
    payload = _evidence(); _gate(payload, REMOTE_GATE_NAME)["name"] = "backend"
    with pytest.raises(PreflightError, match="duplicate gate name"): VerificationEvidence.from_mapping(payload)


@pytest.mark.parametrize("phase,mode", [("pre_cloud", "build-only"), ("final", "deploy")])
def test_validate_evidence_phase_accepts_current_phase_semantics(phase: str, mode: str) -> None:
    validate_evidence_phase(VerificationEvidence.from_mapping(_evidence(phase=phase)), mode)


@pytest.mark.parametrize("mutation", ["order", "command"])
def test_validate_evidence_phase_rejects_noncanonical_gate_contract(mutation: str) -> None:
    payload = _evidence()
    if mutation == "order": payload["gates"][0], payload["gates"][1] = payload["gates"][1], payload["gates"][0]  # type: ignore[index]
    else: _gate(payload, "backend")["command"] = "pytest"
    with pytest.raises(PreflightError, match="canonical"): validate_evidence_phase(VerificationEvidence.from_mapping(payload), "build-only")


@pytest.mark.parametrize("status", ["failed", "pending"])
def test_validate_evidence_phase_requires_pre_cloud_gates_passed(status: str) -> None:
    payload = _evidence(); gate = _gate(payload, "backend")
    gate["status"] = status; gate["completedAt"] = None if status == "pending" else "2026-08-22T12:20:00Z"
    gate["logSha256"] = None if status == "pending" else "d" * 64
    with pytest.raises(PreflightError, match="pre-cloud gate backend must be passed"):
        validate_evidence_phase(VerificationEvidence.from_mapping(payload), "build-only")


def test_remote_execution_is_exact_bounded_policy_bound_and_ordered() -> None:
    assert VerificationEvidence.from_mapping(_evidence(phase="final")).remote_execution is not None
    mutations = (
        lambda value: value.update({"unknown": True}), lambda value: value.update({"sdkVersion": "0.206.0"}),
        lambda value: value.update({"requestedGpuOrder": ["H100", "RTX-PRO-6000"]}),
        lambda value: value.update({"startedAt": "2026-08-22T11:59:00Z"}),
        lambda value: value.update({"deletionConfirmed": False}), lambda value: value.update({"runpodMutationOccurred": True}),
        lambda value: value["commandResults"][0].update({"stdout": "token=secret"}),
        lambda value: value["commandResults"].append(value["commandResults"][0]),
        lambda value: value["uploads"].append(value["uploads"][0]),
    )
    for mutate in mutations:
        payload = json.loads(json.dumps(_evidence(phase="final"))); mutate(payload["remoteExecution"])
        with pytest.raises(PreflightError): VerificationEvidence.from_mapping(payload)


def test_final_evidence_rejects_nonzero_remote_command_exit() -> None:
    payload = _evidence(phase="final")
    payload["remoteExecution"]["commandResults"][0]["exitCode"] = 1  # type: ignore[index]
    with pytest.raises(PreflightError, match="exitCode"):
        VerificationEvidence.from_mapping(payload)


@pytest.mark.parametrize("field", ["command", "stdout", "stderr"])
def test_python_and_schema_reject_secret_bearing_remote_command_text(field: str) -> None:
    from jsonschema import Draft202012Validator

    payload = _evidence(phase="final")
    payload["remoteExecution"]["commandResults"][0][field] = "token=secret"  # type: ignore[index]
    schema = json.loads(
        (Path(__file__).parents[1] / "release/verification_schema.json").read_text()
    )
    with pytest.raises(PreflightError, match="secret-bearing"):
        VerificationEvidence.from_mapping(payload)
    assert list(Draft202012Validator(schema).iter_errors(payload))


def test_python_and_schema_reject_secret_bearing_transfer_name() -> None:
    from jsonschema import Draft202012Validator

    payload = _evidence(phase="final")
    payload["remoteExecution"]["uploads"][0]["name"] = "api_key=secret"  # type: ignore[index]
    schema = json.loads(
        (Path(__file__).parents[1] / "release/verification_schema.json").read_text()
    )
    with pytest.raises(PreflightError, match="secret-bearing"):
        VerificationEvidence.from_mapping(payload)
    assert list(Draft202012Validator(schema).iter_errors(payload))


@pytest.mark.parametrize("unsafe", [
    "nul\0byte", "DaYtOnA-aPi_KeY", "Bearer SECRET", "Set-Cookie: value",
    "API_KEY=secret", "access-token=value", "refresh token=value", "auth_token=value",
    "id-token=value", "ToKeN=secret", "Secrets=value", "pass_word=value", "passwd=value",
    "Authorization=value", "Authentication=value", "auth=value", "auth_header=value",
    "authorization-header=value", "Cookie=value", "credentials=value",
    "AWS_SECRET_ACCESS_KEY=secret", "secret-key=value", "private_key=secret",
    "access_key_id=secret",
])
def test_python_and_schema_safe_text_parity_for_nul_and_case_variants(unsafe: str) -> None:
    from jsonschema import Draft202012Validator

    payload = _evidence(phase="final")
    payload["remoteExecution"]["commandResults"][0]["stdout"] = unsafe  # type: ignore[index]
    schema = json.loads(
        (Path(__file__).parents[1] / "release/verification_schema.json").read_text()
    )
    with pytest.raises(PreflightError):
        VerificationEvidence.from_mapping(payload)
    assert list(Draft202012Validator(schema).iter_errors(payload))


@pytest.mark.parametrize("safe", ["tokenizer ready", "secretary", "authentic", "mytokenvalue", "GPU ready"])
def test_python_and_schema_safe_text_parity_accepts_safe_controls(safe: str) -> None:
    from jsonschema import Draft202012Validator

    payload = _evidence(phase="final")
    payload["remoteExecution"]["commandResults"][0]["stdout"] = safe  # type: ignore[index]
    schema = json.loads(
        (Path(__file__).parents[1] / "release/verification_schema.json").read_text()
    )
    VerificationEvidence.from_mapping(payload)
    assert list(Draft202012Validator(schema).iter_errors(payload)) == []


def test_phase_remote_execution_nullability_is_strict() -> None:
    pre_cloud = _evidence(); pre_cloud["remoteExecution"] = _remote_execution()
    final = _evidence(phase="final"); final["remoteExecution"] = None
    for payload, mode in ((pre_cloud, "build-only"), (final, "deploy")):
        with pytest.raises(PreflightError, match="remoteExecution"):
            validate_evidence_phase(VerificationEvidence.from_mapping(payload), mode)


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("startedAt", "2026-08-22T11:59:00Z", "timestamps must be ordered"),
        ("deletedAt", "2026-08-22T12:31:00Z", "deletedAt must equal.*gate"),
    ],
)
def test_final_remote_chronology_is_bound_to_gate_13(
    field: str, value: str, match: str
) -> None:
    payload = _evidence(phase="final")
    payload["remoteExecution"][field] = value  # type: ignore[index]
    with pytest.raises(PreflightError, match=match):
        VerificationEvidence.from_mapping(payload)


def test_remote_timestamps_participate_in_evidence_freshness() -> None:
    payload = _evidence(phase="final")
    for field, value in zip(
        ("createdAt", "startedAt", "completedAt", "deletedAt"),
        ("2026-08-20T12:00:00Z", "2026-08-20T12:01:00Z", "2026-08-20T12:18:00Z", "2026-08-20T12:19:00Z"),
        strict=True,
    ):
        payload["remoteExecution"][field] = value  # type: ignore[index]
    _gate(payload, REMOTE_GATE_NAME)["completedAt"] = "2026-08-20T12:19:00Z"
    evidence = VerificationEvidence.from_mapping(payload)
    with pytest.raises(PreflightError, match="remoteExecution createdAt is stale"):
        validate_evidence_freshness(
            evidence, datetime(2026, 8, 22, 13, tzinfo=timezone.utc), 175500
        )


def test_record_verifier_success_publishes_canonical_receipt_with_real_log_metadata(
    receipt_repo: Path,
) -> None:
    receipt = _record_receipt(receipt_repo)
    path = receipt_repo / ".verification/receipt.json"
    assert path.read_text() == json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n"
    assert receipt["schemaVersion"] == 1
    assert receipt["repositoryCommit"] == _git(receipt_repo, "rev-parse", "HEAD")
    assert receipt["manifestSha256"] == hashlib.sha256(
        (receipt_repo / "backend/release/v7.3.json").read_bytes()
    ).hexdigest()
    assert receipt["createdAt"] == "2026-08-22T12:30:00Z"
    assert tuple((gate["name"], gate["command"]) for gate in receipt["gates"]) == tuple(  # type: ignore[union-attr]
        REQUIRED_GATE_COMMANDS.items()
    )[:-1]
    for gate in receipt["gates"]:  # type: ignore[union-attr]
        log = receipt_repo / ".verification/logs" / f"{gate['name']}.log"
        assert gate["logSha256"] == hashlib.sha256(log.read_bytes()).hexdigest()


@pytest.mark.parametrize("attack", ["missing", "symlink", "directory", "escaped"])
def test_record_verifier_success_rejects_unsafe_logs(
    receipt_repo: Path, tmp_path: Path, attack: str
) -> None:
    log = receipt_repo / ".verification/logs/backend.log"
    if attack == "missing":
        log.unlink()
    elif attack == "symlink":
        log.unlink(); log.symlink_to(tmp_path / "external.log")
    elif attack == "directory":
        log.unlink(); log.mkdir()
    else:
        shutil.rmtree(receipt_repo / ".verification/logs")
        (receipt_repo / ".verification/logs").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises((OSError, PreflightError), match="(log|regular|unsafe|symlink)"):
        _record_receipt(receipt_repo)
    assert not (receipt_repo / ".verification/receipt.json").exists()


def test_record_verifier_success_rejects_reordered_or_post_receipt_logs(
    receipt_repo: Path,
) -> None:
    backend = receipt_repo / ".verification/logs/backend.log"
    timestamp = datetime(2026, 8, 22, 12, 30, 1, tzinfo=timezone.utc).timestamp()
    os.utime(backend, (timestamp, timestamp))
    with pytest.raises(PreflightError, match="(ordered|after receipt)"):
        _record_receipt(receipt_repo)


@pytest.mark.parametrize("attack", ["dirty", "untracked-manifest", "missing-manifest", "overwrite"])
def test_record_verifier_success_rejects_invalid_repository_state(
    receipt_repo: Path, attack: str
) -> None:
    manifest = receipt_repo / "backend/release/v7.3.json"
    if attack == "dirty":
        manifest.write_bytes(manifest.read_bytes() + b" ")
    elif attack == "untracked-manifest":
        _git(receipt_repo, "rm", "--cached", "backend/release/v7.3.json")
    elif attack == "missing-manifest":
        manifest.unlink()
    else:
        _record_receipt(receipt_repo)


def test_record_verifier_success_rejects_untracked_python_module(receipt_repo: Path) -> None:
    (receipt_repo / "backend/untracked.py").write_text("raise SystemExit\n")
    with pytest.raises(PreflightError, match="untracked.py"):
        _record_receipt(receipt_repo)


def test_receipt_rejects_untracked_file_hidden_by_inherited_global_excludes(
    receipt_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    excluded = receipt_repo / "backend/untracked.py"
    excluded.write_text("raise SystemExit\n")
    excludes = tmp_path / "global-excludes"
    excludes.write_text("backend/untracked.py\n")
    config = tmp_path / "global-gitconfig"
    _git(receipt_repo, "config", "--file", str(config), "core.excludesFile", str(excludes))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))

    with pytest.raises(PreflightError, match="untracked.py"):
        _record_receipt(receipt_repo)


@pytest.mark.parametrize("flag,label", [
    ("--assume-unchanged", "assume-unchanged"),
    ("--skip-worktree", "skip-worktree"),
])
def test_receipt_rejects_hidden_index_flags(
    receipt_repo: Path, flag: str, label: str
) -> None:
    path = "backend/release/v7.3.json"
    _git(receipt_repo, "update-index", flag, "--", path)

    with pytest.raises(PreflightError, match=rf"{label}.*{path}"):
        _record_receipt(receipt_repo)


def test_receipt_hashes_logs_without_buffering_them(
    receipt_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.scripts import write_verification_evidence as writer

    original = writer._read_regular

    def reject_buffered_log(path: Path, label: str):
        if label.startswith("verification log "):
            raise AssertionError("verification logs must be streamed")
        return original(path, label)

    monkeypatch.setattr(writer, "_read_regular", reject_buffered_log)
    receipt = _record_receipt(receipt_repo)
    writer.write_verification_evidence(
        receipt_repo / "evidence.json", phase="pre_cloud", repo_root=receipt_repo,
        now=datetime(2026, 8, 22, 12, 31, tzinfo=timezone.utc),
    )
    assert receipt["gates"]


def test_regular_file_identity_includes_ctime(receipt_repo: Path) -> None:
    from backend.scripts import write_verification_evidence as writer
    from types import SimpleNamespace

    status = (receipt_repo / ".verification/logs/backend.log").stat()
    changed = SimpleNamespace(
        st_dev=status.st_dev, st_ino=status.st_ino, st_size=status.st_size,
        st_mtime_ns=status.st_mtime_ns, st_ctime_ns=status.st_ctime_ns + 1,
    )
    assert writer._file_identity(status) != writer._file_identity(changed)


@pytest.mark.parametrize("variable", ["GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"])
def test_receipt_git_helpers_ignore_repository_redirection(
    receipt_repo: Path, monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    expected = _git(receipt_repo, "rev-parse", "HEAD")
    monkeypatch.setenv(variable, "/definitely/not/the/repository")
    assert _record_receipt(receipt_repo)["repositoryCommit"] == expected
    with pytest.raises((OSError, PreflightError, FileExistsError)):
        _record_receipt(receipt_repo)


def test_writer_publishes_receipt_backed_pre_cloud_evidence_and_never_clobbers(
    receipt_repo: Path, tmp_path: Path
) -> None:
    from backend.app.release_manifest import load_release_manifest
    from backend.scripts.write_verification_evidence import write_verification_evidence

    receipt = _record_receipt(receipt_repo)
    output = tmp_path / "evidence.json"
    kwargs = dict(
        phase="pre_cloud", repo_root=receipt_repo,
        now=datetime(2026, 8, 22, 12, 31, tzinfo=timezone.utc),
    )
    evidence = write_verification_evidence(output, **kwargs)
    assert output.read_text() == json.dumps(evidence.to_mapping(), sort_keys=True, separators=(",", ":")) + "\n"
    assert evidence.source_commit == load_release_manifest(
        receipt_repo / "backend/release/v7.3.json"
    ).source_commit
    assert evidence.verification_commit == receipt["repositoryCommit"]
    assert [gate.to_mapping() for gate in evidence.gates[:-1]] == [
        {**gate, "status": "passed"} for gate in receipt["gates"]  # type: ignore[union-attr]
    ]
    assert evidence.gates[-1].completed_at is None
    assert evidence.gates[-1].log_sha256 is None
    with pytest.raises(FileExistsError):
        write_verification_evidence(output, **kwargs)


@pytest.mark.parametrize(
    "attack",
    ["missing", "symlink", "directory", "malformed", "unknown", "type", "stale", "manifest", "commit", "digest", "mtime", "order", "command"],
)
def test_writer_rejects_invalid_or_tampered_receipt_before_publication(
    receipt_repo: Path, tmp_path: Path, attack: str
) -> None:
    from backend.scripts.write_verification_evidence import write_verification_evidence

    receipt = _record_receipt(receipt_repo)
    path = receipt_repo / ".verification/receipt.json"
    if attack == "missing":
        path.unlink()
    elif attack == "symlink":
        external = tmp_path / "external-receipt.json"
        path.replace(external); path.symlink_to(external)
    elif attack == "directory":
        path.unlink(); path.mkdir()
    elif attack == "malformed":
        path.write_text("{", encoding="utf-8")
    else:
        if attack == "unknown": receipt["unknown"] = True
        elif attack == "type": receipt["repositoryCommit"] = 7
        elif attack == "stale": receipt["createdAt"] = "2026-08-20T12:30:00Z"
        elif attack == "manifest": receipt["manifestSha256"] = "a" * 64
        elif attack == "commit": receipt["repositoryCommit"] = "a" * 40
        elif attack == "digest": (receipt_repo / ".verification/logs/backend.log").write_text("changed")
        elif attack == "mtime":
            log = receipt_repo / ".verification/logs/backend.log"
            timestamp = datetime(2026, 8, 22, 12, 0, 30, tzinfo=timezone.utc).timestamp()
            os.utime(log, (timestamp, timestamp))
        elif attack == "order": receipt["gates"][0], receipt["gates"][1] = receipt["gates"][1], receipt["gates"][0]  # type: ignore[index]
        else: receipt["gates"][0]["command"] = "pytest"  # type: ignore[index]
        if attack not in {"digest", "mtime"}:
            path.write_text(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n")
    output = tmp_path / "evidence.json"
    with pytest.raises((OSError, PreflightError, ValueError)):
        write_verification_evidence(
            output, phase="pre_cloud", repo_root=receipt_repo,
            now=datetime(2026, 8, 22, 12, 31, tzinfo=timezone.utc),
        )
    assert not output.exists()


@pytest.mark.parametrize("tool_versions", [
    {"python": "0.0.0"}, {"python": "3.11.9", "unknown": "1"},
    {"python": "x" * 1024}, {"python": "token=secret"},
])
def test_writer_rejects_nonlocal_or_unsafe_receipt_tool_versions(
    receipt_repo: Path, tmp_path: Path, tool_versions: dict[str, str]
) -> None:
    from backend.scripts.write_verification_evidence import write_verification_evidence

    receipt = _record_receipt(receipt_repo)
    receipt["toolVersions"] = tool_versions
    (receipt_repo / ".verification/receipt.json").write_text(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n"
    )
    with pytest.raises(PreflightError, match="toolVersions"):
        write_verification_evidence(
            tmp_path / "evidence.json", phase="pre_cloud", repo_root=receipt_repo,
            now=datetime(2026, 8, 22, 12, 31, tzinfo=timezone.utc),
        )


def test_final_writer_rejects_failed_smoke_report(
    receipt_repo: Path, tmp_path: Path
) -> None:
    from backend.app.remote_contracts import canonical_json_bytes
    from backend.scripts.write_verification_evidence import write_verification_evidence

    _record_receipt(receipt_repo)
    failure = {
        "mode": "real-smoke",
        "status": "failed",
        "error": "Daytona smoke command failed",
        "commandResult": {
            "stage": "worker-import", "exitCode": 9,
            "stdout": "", "stderr": "ImportError: missing library",
        },
    }
    remote = tmp_path / "failed-smoke.json"
    remote.write_bytes(canonical_json_bytes(failure))
    output = tmp_path / "final-evidence.json"

    with pytest.raises(PreflightError, match="remoteExecution missing keys"):
        write_verification_evidence(
            output,
            phase="final",
            repo_root=receipt_repo,
            remote_execution_path=remote,
            now=datetime(2026, 8, 22, 12, 31, tzinfo=timezone.utc),
        )

    assert not output.exists()


def test_final_writer_rejects_manifest_changed_after_receipt(
    receipt_repo: Path, tmp_path: Path
) -> None:
    from backend.app.remote_contracts import canonical_json_bytes
    from backend.scripts.write_verification_evidence import write_verification_evidence

    _record_receipt(receipt_repo)
    manifest_path = receipt_repo / "backend/release/v7.3.json"
    manifest = json.loads(manifest_path.read_text()); manifest["createdAt"] = "2026-08-22T12:01:00Z"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    _git(receipt_repo, "add", manifest_path.relative_to(receipt_repo).as_posix())
    _git(receipt_repo, "commit", "-m", "changed manifest")
    remote = tmp_path / "remote.json"; remote.write_bytes(canonical_json_bytes(_remote_execution()))

    with pytest.raises(PreflightError, match="manifest digest"):
        write_verification_evidence(
            tmp_path / "evidence.json", phase="final", repo_root=receipt_repo,
            remote_execution_path=remote,
            now=datetime(2026, 8, 22, 12, 31, tzinfo=timezone.utc),
        )


def test_final_writer_binds_remote_gate_to_canonical_input(
    receipt_repo: Path, tmp_path: Path
) -> None:
    from backend.app.remote_contracts import canonical_json_bytes
    from backend.scripts.write_verification_evidence import write_verification_evidence

    receipt = _record_receipt(receipt_repo)
    metadata = receipt_repo / "docs/status/current.md"
    metadata.parent.mkdir(parents=True); metadata.write_text("verified\n")
    _git(receipt_repo, "add", "docs/status/current.md"); _git(receipt_repo, "commit", "-m", "evidence metadata")
    from backend.app.daytona_worker_image import repository_worker_context_sha256
    from backend.app.release_manifest import load_release_manifest

    remote_payload = _remote_execution()
    remote_payload.update({
        "sourceCommit": load_release_manifest(receipt_repo / "backend/release/v7.3.json").source_commit,
        "verificationCommit": receipt["repositoryCommit"],
        "manifestSha256": receipt["manifestSha256"],
        "workerContextSha256": repository_worker_context_sha256(receipt_repo),
    })
    remote = tmp_path / "remote.json"; remote.write_bytes(canonical_json_bytes(remote_payload))
    evidence = write_verification_evidence(
        tmp_path / "evidence.json", phase="final", repo_root=receipt_repo,
        remote_execution_path=remote,
        now=datetime(2026, 8, 22, 12, 31, tzinfo=timezone.utc),
    )
    gate = evidence.gates[-1]
    assert evidence.verification_commit == receipt["repositoryCommit"]
    assert gate.completed_at == datetime(2026, 8, 22, 12, 30, 4, tzinfo=timezone.utc)
    assert gate.log_sha256 == hashlib.sha256(remote.read_bytes()).hexdigest()


def test_writer_parses_the_manifest_bytes_it_hashed(
    receipt_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.scripts import write_verification_evidence as writer

    _record_receipt(receipt_repo)
    parsed = []
    release_manifest = writer.ReleaseManifest
    class SpyManifest:
        @staticmethod
        def from_mapping(value):
            parsed.append(value)
            return release_manifest.from_mapping(value)
    monkeypatch.setattr(writer, "ReleaseManifest", SpyManifest)
    evidence = writer.write_verification_evidence(
        tmp_path / "evidence.json", phase="pre_cloud", repo_root=receipt_repo,
        now=datetime(2026, 8, 22, 12, 31, tzinfo=timezone.utc),
    )
    assert evidence.manifest_sha256 == hashlib.sha256(
        (receipt_repo / "backend/release/v7.3.json").read_bytes()
    ).hexdigest()
    assert parsed == [json.loads((receipt_repo / "backend/release/v7.3.json").read_bytes())]


@pytest.mark.parametrize(
    "field,bad",
    [
        ("sourceCommit", "f" * 40),
        ("verificationCommit", "f" * 40),
        ("manifestSha256", "f" * 64),
        ("workerContextSha256", "f" * 64),
    ],
)
def test_final_writer_rejects_remote_release_binding_mismatch(
    receipt_repo: Path, tmp_path: Path, field: str, bad: str
) -> None:
    from backend.app.daytona_worker_image import repository_worker_context_sha256
    from backend.app.release_manifest import load_release_manifest
    from backend.app.remote_contracts import canonical_json_bytes
    from backend.scripts.write_verification_evidence import write_verification_evidence

    receipt = _record_receipt(receipt_repo)
    metadata = receipt_repo / "docs/status/current.md"
    metadata.parent.mkdir(parents=True); metadata.write_text("verified\n")
    _git(receipt_repo, "add", "docs/status/current.md"); _git(receipt_repo, "commit", "-m", "metadata")
    remote_payload = _remote_execution()
    remote_payload.update({
        "sourceCommit": load_release_manifest(receipt_repo / "backend/release/v7.3.json").source_commit,
        "verificationCommit": receipt["repositoryCommit"],
        "manifestSha256": receipt["manifestSha256"],
        "workerContextSha256": repository_worker_context_sha256(receipt_repo),
        field: bad,
    })
    remote = tmp_path / "remote.json"; remote.write_bytes(canonical_json_bytes(remote_payload))
    with pytest.raises(PreflightError, match=field):
        write_verification_evidence(
            tmp_path / "evidence.json", phase="final", repo_root=receipt_repo,
            remote_execution_path=remote,
            now=datetime(2026, 8, 22, 12, 31, tzinfo=timezone.utc),
        )


def test_final_writer_rejects_remote_created_before_verifier_receipt(
    receipt_repo: Path, tmp_path: Path
) -> None:
    from backend.app.daytona_worker_image import repository_worker_context_sha256
    from backend.app.release_manifest import load_release_manifest
    from backend.app.remote_contracts import canonical_json_bytes
    from backend.scripts.write_verification_evidence import write_verification_evidence

    receipt = _record_receipt(receipt_repo)
    metadata = receipt_repo / "docs/status/current.md"
    metadata.parent.mkdir(parents=True); metadata.write_text("verified\n")
    _git(receipt_repo, "add", "docs/status/current.md"); _git(receipt_repo, "commit", "-m", "metadata")
    remote_payload = _remote_execution()
    remote_payload.update({
        "sourceCommit": load_release_manifest(receipt_repo / "backend/release/v7.3.json").source_commit,
        "verificationCommit": receipt["repositoryCommit"],
        "manifestSha256": receipt["manifestSha256"],
        "workerContextSha256": repository_worker_context_sha256(receipt_repo),
        "createdAt": "2026-08-22T12:29:56Z", "startedAt": "2026-08-22T12:29:57Z",
        "completedAt": "2026-08-22T12:29:58Z", "deletedAt": "2026-08-22T12:29:59Z",
    })
    remote = tmp_path / "remote.json"; remote.write_bytes(canonical_json_bytes(remote_payload))
    with pytest.raises(PreflightError, match="predates verifier receipt"):
        write_verification_evidence(
            tmp_path / "evidence.json", phase="final", repo_root=receipt_repo,
            remote_execution_path=remote,
            now=datetime(2026, 8, 22, 12, 31, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize("attack", ["parent", "output"])
def test_writer_rejects_symlinked_publication_paths(
    receipt_repo: Path, tmp_path: Path, attack: str
) -> None:
    from backend.scripts.write_verification_evidence import write_verification_evidence

    _record_receipt(receipt_repo)

    real = tmp_path / "real"; real.mkdir()
    parent = tmp_path / "publish"
    output = parent / "evidence.json"
    if attack == "parent": parent.symlink_to(real, target_is_directory=True)
    else:
        parent.mkdir(); output.symlink_to(real / "victim.json")
    with pytest.raises(OSError):
        write_verification_evidence(
            output, phase="pre_cloud", repo_root=receipt_repo,
            now=datetime(2026, 8, 22, 12, 31, tzinfo=timezone.utc),
        )
    assert not (real / "evidence.json").exists() and not (real / "victim.json").exists()


def test_writer_rejects_parent_swap_without_publication(
    receipt_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.scripts import write_verification_evidence as writer

    _record_receipt(receipt_repo)

    parent = tmp_path / "publish"; parent.mkdir(); displaced = tmp_path / "displaced"
    original_link = writer.os.link
    def swap_then_link(*args, **kwargs):
        parent.rename(displaced); parent.mkdir(); return original_link(*args, **kwargs)
    monkeypatch.setattr(writer.os, "link", swap_then_link)
    with pytest.raises(OSError, match="changed"):
        writer.write_verification_evidence(
            parent / "evidence.json", phase="pre_cloud", repo_root=receipt_repo,
            now=datetime(2026, 8, 22, 12, 31, tzinfo=timezone.utc),
        )
    assert not (parent / "evidence.json").exists()
    assert not (displaced / "evidence.json").exists()


def test_writer_rolls_back_when_post_link_identity_check_raises(
    receipt_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.scripts import write_verification_evidence as writer

    _record_receipt(receipt_repo)

    output = tmp_path / "evidence.json"
    original_identity = writer._parent_identity
    calls = 0
    def fail_after_link(path: Path):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected post-link identity failure")
        return original_identity(path)
    monkeypatch.setattr(writer, "_parent_identity", fail_after_link)
    with pytest.raises(OSError, match="injected post-link"):
        writer.write_verification_evidence(
            output, phase="pre_cloud", repo_root=receipt_repo,
            now=datetime(2026, 8, 22, 12, 31, tzinfo=timezone.utc),
        )
    assert not output.exists()
    assert list(tmp_path.glob(".*.tmp")) == []


def test_validate_evidence_freshness_preserves_exact_behavior() -> None:
    evidence = VerificationEvidence.from_mapping(_evidence())
    validate_evidence_freshness(evidence, datetime(2026, 8, 22, 13, tzinfo=timezone.utc), 86400)
    for now, match in ((datetime(2026, 8, 22, 12, tzinfo=timezone.utc), "future"), (datetime(2026, 8, 24, 13, tzinfo=timezone.utc), "stale"), (datetime(2026, 8, 22, 13), "timezone")):
        with pytest.raises(PreflightError, match=match): validate_evidence_freshness(evidence, now, 86400)


def test_evidence_validity_window_warns_before_the_oldest_gate_expires() -> None:
    evidence = VerificationEvidence.from_mapping(_evidence())
    now = datetime(2026, 8, 23, 8, 20, tzinfo=timezone.utc)

    assert validate_evidence_validity_window(evidence, now, 86400, 4 * 60 * 60) == 4 * 60 * 60
    with pytest.raises(PreflightError, match="expires too soon"):
        validate_evidence_validity_window(evidence, now, 86400, 4 * 60 * 60 + 1)
