"""Record verifier success and publish receipt-backed release evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import secrets
import stat
import subprocess
from typing import Mapping, Sequence

from backend.app.release_manifest import ReleaseManifest
from backend.app.remote_contracts import canonical_json_bytes, load_canonical_json
from backend.release.evidence import (
    MAX_EVIDENCE_AGE_SECONDS, REMOTE_GATE_NAME, REQUIRED_GATE_COMMANDS, SHA256_RE,
    SOURCE_COMMIT_RE, PreflightError, VerificationEvidence, _exact_keys,
    _format_timestamp, _nonempty_string, _timestamp,
    _git_environment, _reject_hidden_index_entries,
)


_DIRECTORY_FLAGS = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
_FILE_FLAGS = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
_MANIFEST_PATH = Path("backend/release/v7.3.json")
_RECEIPT_PATH = Path(".verification/receipt.json")
_LOG_DIR = Path(".verification/logs")
_RECEIPT_KEYS = frozenset({"schemaVersion", "repositoryCommit", "manifestSha256", "createdAt", "toolVersions", "gates"})
_RECEIPT_GATE_KEYS = frozenset({"name", "command", "completedAt", "logSha256"})


def _open_output_parent(output: Path) -> int:
    absolute = output.absolute()
    if not absolute.name or any(part in {".", ".."} for part in absolute.parts):
        raise OSError("output path is invalid")
    descriptor = os.open("/", _DIRECTORY_FLAGS)
    try:
        for part in absolute.parent.parts[1:]:
            try:
                os.mkdir(part, 0o755, dir_fd=descriptor)
            except FileExistsError:
                pass
            next_descriptor = os.open(part, _DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _parent_identity(output: Path) -> tuple[int, int]:
    descriptor = _open_output_parent(output)
    try:
        status = os.fstat(descriptor)
        return status.st_dev, status.st_ino
    finally:
        os.close(descriptor)


def _publish_exclusive(output: Path, content: bytes) -> None:
    output = output.absolute()
    parent_descriptor = _open_output_parent(output)
    parent_status = os.fstat(parent_descriptor)
    parent_identity = (parent_status.st_dev, parent_status.st_ino)
    try:
        os.stat(output.name, dir_fd=parent_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        pass
    else:
        os.close(parent_descriptor)
        raise FileExistsError(f"refusing to overwrite {output}")
    temporary = f".{output.name}.{secrets.token_hex(16)}.tmp"
    temporary_descriptor = -1
    published = False
    try:
        temporary_descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
            0o644,
            dir_fd=parent_descriptor,
        )
        written = 0
        while written < len(content):
            written += os.write(temporary_descriptor, content[written:])
        os.fsync(temporary_descriptor)
        os.close(temporary_descriptor); temporary_descriptor = -1
        if _parent_identity(output) != parent_identity:
            raise OSError("output parent changed before publication")
        os.link(temporary, output.name, src_dir_fd=parent_descriptor, dst_dir_fd=parent_descriptor, follow_symlinks=False)
        published = True
        if _parent_identity(output) != parent_identity:
            raise OSError("output parent changed during publication")
        os.unlink(temporary, dir_fd=parent_descriptor); temporary = ""
        os.fsync(parent_descriptor)
    except BaseException:
        if published:
            try:
                os.unlink(output.name, dir_fd=parent_descriptor)
            except FileNotFoundError:
                pass
            os.fsync(parent_descriptor)
        raise
    finally:
        if temporary_descriptor >= 0:
            os.close(temporary_descriptor)
        if temporary:
            try:
                os.unlink(temporary, dir_fd=parent_descriptor)
            except FileNotFoundError:
                pass
        os.close(parent_descriptor)


def _file_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def _read_regular(path: Path, label: str) -> tuple[bytes, os.stat_result]:
    classified = os.stat(path, follow_symlinks=False)
    if not stat.S_ISREG(classified.st_mode):
        raise OSError(f"{label} must be a regular file")
    descriptor = os.open(path, _FILE_FLAGS)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or _file_identity(opened) != _file_identity(classified):
            raise OSError(f"{label} changed before reading")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        after_read = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    after_path = os.stat(path, follow_symlinks=False)
    if _file_identity(after_read) != _file_identity(opened) or _file_identity(after_path) != _file_identity(opened):
        raise OSError(f"{label} changed while reading")
    return b"".join(chunks), opened


def _hash_regular(path: Path, label: str) -> tuple[str, os.stat_result]:
    classified = os.stat(path, follow_symlinks=False)
    if not stat.S_ISREG(classified.st_mode):
        raise OSError(f"{label} must be a regular file")
    descriptor = os.open(path, _FILE_FLAGS)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or _file_identity(opened) != _file_identity(classified):
            raise OSError(f"{label} changed before reading")
        digest = hashlib.sha256()
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
        after_read = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    after_path = os.stat(path, follow_symlinks=False)
    if _file_identity(after_read) != _file_identity(opened) or _file_identity(after_path) != _file_identity(opened):
        raise OSError(f"{label} changed while reading")
    return digest.hexdigest(), opened


def _safe_directory(path: Path, label: str) -> None:
    status = os.stat(path, follow_symlinks=False)
    if not stat.S_ISDIR(status.st_mode) or path.resolve() != path.absolute():
        raise OSError(f"{label} must be an unescaped regular directory")


def _mtime_timestamp(status: os.stat_result) -> str:
    seconds, nanoseconds = divmod(status.st_mtime_ns, 1_000_000_000)
    value = datetime.fromtimestamp(seconds, timezone.utc).replace(microsecond=nanoseconds // 1000)
    return _format_timestamp(value)


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args], check=check, capture_output=True,
            text=True, env=_git_environment(),
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PreflightError(f"git {' '.join(args)} failed: {exc}") from exc


def _clean_head(root: Path) -> str:
    _reject_hidden_index_entries(_git(root, "ls-files", "-v", "-z").stdout)
    status = _git(root, "status", "--porcelain", "--untracked-files=no").stdout
    if status:
        raise PreflightError("tracked worktree must be clean")
    allowed = {_RECEIPT_PATH.as_posix()} | {
        (_LOG_DIR / f"{name}.log").as_posix() for name, _ in _local_gate_items()
    }
    untracked = set(filter(None, _git(
        root, "ls-files", "--others", "--exclude-standard", "-z"
    ).stdout.split("\0")))
    if unexpected := sorted(untracked - allowed):
        raise PreflightError("untracked worktree files are forbidden: " + ", ".join(unexpected))
    head = _git(root, "rev-parse", "--verify", "HEAD^{commit}").stdout.strip()
    if SOURCE_COMMIT_RE.fullmatch(head) is None:
        raise PreflightError("repository HEAD must be a lower-case 40-character SHA")
    return head


def _manifest_bytes(root: Path) -> bytes:
    tracked = _git(root, "ls-files", "--error-unmatch", "--", _MANIFEST_PATH.as_posix(), check=False)
    if tracked.returncode != 0:
        raise PreflightError("release manifest must be tracked")
    content, _ = _read_regular(root / _MANIFEST_PATH, "release manifest")
    return content


def _now(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise PreflightError("current time must include a timezone")
    return result.astimezone(timezone.utc)


def _local_gate_items() -> tuple[tuple[str, str], ...]:
    return tuple(REQUIRED_GATE_COMMANDS.items())[:-1]


def record_verifier_success(repo_root: Path | str, *, now: datetime | None = None) -> dict[str, object]:
    root = Path(repo_root).resolve(strict=True)
    current = _now(now)
    verification_dir = root / ".verification"
    log_dir = root / _LOG_DIR
    _safe_directory(verification_dir, "verification directory")
    _safe_directory(log_dir, "verification log directory")
    head = _clean_head(root)
    manifest = _manifest_bytes(root)
    gates: list[dict[str, object]] = []
    completed: list[datetime] = []
    for name, command in _local_gate_items():
        if Path(name).name != name:
            raise PreflightError("verification log name escapes log directory")
        digest, status = _hash_regular(log_dir / f"{name}.log", f"verification log {name}")
        completed_at = _mtime_timestamp(status)
        parsed_completed = _timestamp(completed_at, f"verification log {name} completedAt")
        if parsed_completed > current:
            raise PreflightError(f"verification log {name} is after receipt creation")
        completed.append(parsed_completed)
        gates.append({"name": name, "command": command, "completedAt": completed_at,
                      "logSha256": digest})
    if completed != sorted(completed):
        raise PreflightError("verification log completion timestamps must be ordered")
    if _clean_head(root) != head:
        raise PreflightError("repository HEAD changed during receipt recording")
    receipt: dict[str, object] = {
        "schemaVersion": 1, "repositoryCommit": head,
        "manifestSha256": hashlib.sha256(manifest).hexdigest(),
        "createdAt": _format_timestamp(current),
        "toolVersions": _local_tool_versions(), "gates": gates,
    }
    _publish_exclusive(root / _RECEIPT_PATH, canonical_json_bytes(receipt))
    return receipt


def _local_tool_versions() -> dict[str, str]:
    version = os.sys.version_info
    return {"python": f"{version.major}.{version.minor}.{version.micro}"}


def _validate_tool_versions(value: object) -> dict[str, str]:
    expected = _local_tool_versions()
    if not isinstance(value, Mapping) or dict(value) != expected:
        raise PreflightError("receipt toolVersions must exactly match locally derived versions")
    return expected


def _load_verifier_receipt(root: Path, now: datetime) -> dict[str, object]:
    _safe_directory(root / ".verification", "verification directory")
    _safe_directory(root / _LOG_DIR, "verification log directory")
    raw, _ = _read_regular(root / _RECEIPT_PATH, "verification receipt")
    value = load_canonical_json(raw)
    if not isinstance(value, Mapping):
        raise PreflightError("verification receipt must be an object")
    _exact_keys(value, _RECEIPT_KEYS, "verification receipt")
    if type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1:
        raise PreflightError("verification receipt schemaVersion must be 1")
    commit = _nonempty_string(value["repositoryCommit"], "receipt repositoryCommit")
    if SOURCE_COMMIT_RE.fullmatch(commit) is None:
        raise PreflightError("receipt repositoryCommit must be a lower-case 40-character SHA")
    manifest_sha = _nonempty_string(value["manifestSha256"], "receipt manifestSha256")
    if SHA256_RE.fullmatch(manifest_sha) is None:
        raise PreflightError("receipt manifestSha256 must be a lower-case SHA-256")
    created_at = _timestamp(value["createdAt"], "receipt createdAt")
    age = (now - created_at).total_seconds()
    if age < 0:
        raise PreflightError("verification receipt is from the future")
    if age > MAX_EVIDENCE_AGE_SECONDS:
        raise PreflightError("verification receipt is stale")
    tool_versions = _validate_tool_versions(value["toolVersions"])
    raw_gates = value["gates"]
    if not isinstance(raw_gates, list) or len(raw_gates) != len(_local_gate_items()):
        raise PreflightError("verification receipt must contain the exact local gate inventory")
    gates: list[dict[str, object]] = []
    completed: list[datetime] = []
    for raw_gate, (expected_name, expected_command) in zip(raw_gates, _local_gate_items(), strict=True):
        if not isinstance(raw_gate, Mapping):
            raise PreflightError("verification receipt gate must be an object")
        _exact_keys(raw_gate, _RECEIPT_GATE_KEYS, "verification receipt gate")
        if raw_gate["name"] != expected_name or raw_gate["command"] != expected_command:
            raise PreflightError("verification receipt gates must use canonical order and commands")
        completed_at = _timestamp(raw_gate["completedAt"], f"receipt gate {expected_name} completedAt")
        digest = _nonempty_string(raw_gate["logSha256"], f"receipt gate {expected_name} logSha256")
        if SHA256_RE.fullmatch(digest) is None:
            raise PreflightError(f"receipt gate {expected_name} logSha256 is invalid")
        actual_digest, status = _hash_regular(root / _LOG_DIR / f"{expected_name}.log", f"verification log {expected_name}")
        if actual_digest != digest:
            raise PreflightError(f"verification log {expected_name} digest mismatch")
        if _mtime_timestamp(status) != raw_gate["completedAt"]:
            raise PreflightError(f"verification log {expected_name} timestamp mismatch")
        if completed_at > created_at:
            raise PreflightError(f"verification log {expected_name} is after receipt creation")
        completed.append(completed_at)
        gates.append(dict(raw_gate))
    if completed != sorted(completed):
        raise PreflightError("verification receipt gate timestamps must be ordered")
    return {"schemaVersion": 1, "repositoryCommit": commit,
            "manifestSha256": manifest_sha, "createdAt": value["createdAt"],
            "toolVersions": tool_versions, "gates": gates}


def _require_commit_binding(root: Path, verification_commit: str, phase: str) -> None:
    head = _clean_head(root)
    if phase == "pre_cloud" and head != verification_commit:
        raise PreflightError("pre_cloud evidence requires HEAD to equal verificationCommit")


def write_verification_evidence(
    output_path: Path | str, *, phase: str, repo_root: Path | str,
    manifest_path: Path | str | None = None,
    remote_execution_path: Path | str | None = None,
    now: datetime | None = None,
) -> VerificationEvidence:
    if phase not in {"pre_cloud", "final"}:
        raise PreflightError("phase must be pre_cloud or final")
    if (phase == "final") != (remote_execution_path is not None):
        raise PreflightError("remote execution is required exactly for final evidence")
    root = Path(repo_root).resolve(strict=True)
    current = _now(now)
    receipt = _load_verifier_receipt(root, current)
    verification_commit = str(receipt["repositoryCommit"])
    _require_commit_binding(root, verification_commit, phase)
    expected_manifest = (root / _MANIFEST_PATH).resolve()
    manifest_source = Path(manifest_path) if manifest_path is not None else expected_manifest
    if not manifest_source.is_absolute():
        manifest_source = root / manifest_source
    if manifest_source.resolve() != expected_manifest:
        raise PreflightError("manifest path must be backend/release/v7.3.json")
    manifest_bytes = _manifest_bytes(root)
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    if manifest_sha != receipt["manifestSha256"]:
        raise PreflightError("release manifest digest does not match verification receipt")
    from backend.release.preflight import _json_bytes_mapping, validate_verification_binding
    validate_verification_binding(
        root, verification_commit, _MANIFEST_PATH.as_posix(), manifest_sha
    )
    manifest = ReleaseManifest.from_mapping(
        _json_bytes_mapping(manifest_bytes, "release manifest")
    )
    gates = [{**gate, "status": "passed"} for gate in receipt["gates"]]  # type: ignore[union-attr]
    remote: object = None
    if remote_execution_path is None:
        gates.append({"name": REMOTE_GATE_NAME, "command": REQUIRED_GATE_COMMANDS[REMOTE_GATE_NAME],
                      "status": "pending", "completedAt": None, "logSha256": None})
    else:
        remote_bytes, _ = _read_regular(Path(remote_execution_path), "remote execution")
        remote = load_canonical_json(remote_bytes)
        if not isinstance(remote, Mapping):
            raise PreflightError("remote execution must be an object")
        from backend.app.daytona_worker_image import repository_worker_context_sha256
        from backend.release.evidence import RemoteExecution

        parsed_remote = RemoteExecution.from_mapping(remote)
        expected_remote = {
            "sourceCommit": manifest.source_commit,
            "verificationCommit": verification_commit,
            "manifestSha256": manifest_sha,
            "workerContextSha256": repository_worker_context_sha256(root),
        }
        for key, expected in expected_remote.items():
            if parsed_remote.value[key] != expected:
                raise PreflightError(f"remote execution {key} does not match verified release")
        if parsed_remote.timestamps[0] < _timestamp(receipt["createdAt"], "receipt createdAt"):
            raise PreflightError("remote execution predates verifier receipt")
        gates.append({"name": REMOTE_GATE_NAME, "command": REQUIRED_GATE_COMMANDS[REMOTE_GATE_NAME],
                      "status": "passed", "completedAt": remote.get("deletedAt"),
                      "logSha256": hashlib.sha256(remote_bytes).hexdigest()})
    payload = {
        "schemaVersion": 2, "phase": phase, "sourceCommit": manifest.source_commit,
        "verificationCommit": verification_commit, "manifestSha256": manifest_sha,
        "createdAt": _format_timestamp(current), "toolVersions": receipt["toolVersions"],
        "gates": gates, "overallPassed": phase == "final", "remoteExecution": remote,
    }
    evidence = VerificationEvidence.from_mapping(payload)
    from backend.release.evidence import validate_evidence_phase
    validate_evidence_phase(evidence, "build-only" if phase == "pre_cloud" else "deploy")
    _publish_exclusive(Path(output_path), canonical_json_bytes(evidence.to_mapping()))
    return evidence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record-verifier-success", action="store_true")
    parser.add_argument("--phase", choices=("pre_cloud", "final"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--remote-execution", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    repo_root = Path(__file__).parents[2]
    if args.record_verifier_success:
        if any(value is not None for value in (args.phase, args.output, args.manifest, args.remote_execution)):
            parser.error("--record-verifier-success is mutually exclusive with evidence options")
        action = lambda: record_verifier_success(repo_root)
    else:
        if args.phase is None or args.output is None:
            parser.error("--phase and --output are required for evidence publication")
        if (args.phase == "final") != (args.remote_execution is not None):
            parser.error("--remote-execution is required exactly for --phase final")
        action = lambda: write_verification_evidence(
            args.output, phase=args.phase, repo_root=repo_root,
            manifest_path=args.manifest, remote_execution_path=args.remote_execution,
        )
    try:
        action()
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
