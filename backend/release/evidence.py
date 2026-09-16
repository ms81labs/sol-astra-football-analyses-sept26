"""Strict parsing and validation for release verification evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
from types import MappingProxyType
from typing import Mapping

from backend.app.release_manifest import ManifestError, load_json_mapping
from backend.app.remote_contracts import MAX_JSON_STRING, _SECRET_TEXT
from backend.release.daytona_policy import load_daytona_policy


SCHEMA_VERSION = 2
REMOTE_GATE_NAME = "daytona-gpu-smoke"
MAX_EVIDENCE_AGE_SECONDS = 24 * 60 * 60
SOURCE_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_GATE_COMMANDS = MappingProxyType(
    {
        "backend": "python3 -m pytest -q backend/tests",
        "sidecar": "python3 -m pytest -q research-addon/tests",
        "frontend-tests": "npm --prefix frontend test -- --run",
        "lint": "npm --prefix frontend run lint",
        "typecheck-app": "cd frontend && npx tsc -p tsconfig.app.json --noEmit --incremental false",
        "typecheck-node": "cd frontend && npx tsc -p tsconfig.node.json --noEmit --incremental false",
        "build": "npm --prefix frontend run build",
        "backend-startup": "python3 -c 'from backend.app.main import app'",
        "manifest": (
            "python3 -m pytest -q backend/tests/test_release_manifest.py "
            "backend/tests/test_write_release_manifest.py"
        ),
        "runtime-options": "python3 -m pytest -q backend/tests/test_runtime_options.py",
        "preflight-negatives": (
            "python3 -m pytest -q backend/tests/test_release_preflight.py -k reject"
        ),
        "prod-audit": "npm --prefix frontend audit --omit=dev --audit-level=high",
        REMOTE_GATE_NAME: "python3 -m backend.scripts.run_daytona_gpu_smoke --real-smoke",
    }
)

_EVIDENCE_KEYS = frozenset(
    {
        "schemaVersion",
        "phase",
        "sourceCommit",
        "verificationCommit",
        "manifestSha256",
        "createdAt",
        "toolVersions",
        "gates",
        "overallPassed",
        "remoteExecution",
    }
)
_GATE_KEYS = frozenset({"name", "command", "status", "completedAt", "logSha256"})
_PHASES = frozenset({"pre_cloud", "final"})
_STATUSES = frozenset({"passed", "failed", "pending"})
_EXACT_UTC_RFC3339 = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,9})?Z$"
)


class PreflightError(ValueError):
    """Raised when a release input fails a preflight safety invariant."""


def _git_environment() -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    return environment


def _reject_hidden_index_entries(output: str) -> None:
    labels = {
        "h": "assume-unchanged",
        "S": "skip-worktree",
        "s": "assume-unchanged and skip-worktree",
    }
    violations = []
    for entry in filter(None, output.split("\0")):
        if len(entry) < 3 or entry[1] != " ":
            raise PreflightError("git index visibility output is invalid")
        if label := labels.get(entry[0]):
            violations.append(f"{label}:{entry[2:]}")
    if violations:
        raise PreflightError(
            "git index visibility flags are forbidden: " + ", ".join(violations)
        )


def _exact_keys(value: Mapping[str, object], expected: frozenset[str], label: str) -> None:
    if any(not isinstance(key, str) for key in value):
        raise PreflightError(f"{label} object keys must be strings")
    missing = sorted(expected - set(value))
    unknown = sorted(set(value) - expected)
    if missing:
        raise PreflightError(f"{label} missing keys: {', '.join(missing)}")
    if unknown:
        raise PreflightError(f"{label} unknown keys: {', '.join(unknown)}")


def _nonempty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PreflightError(f"{label} must be a non-empty string")
    return value


def _timestamp(value: object, label: str) -> datetime:
    raw = _nonempty_string(value, label)
    if _EXACT_UTC_RFC3339.fullmatch(raw) is None:
        raise PreflightError(
            f"{label} must use exact UTC RFC3339 syntax YYYY-MM-DDTHH:MM:SS(.frac)?Z"
        )
    try:
        parsed = datetime.fromisoformat(raw.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise PreflightError(f"{label} must be a valid RFC3339 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PreflightError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class VerificationGate:
    name: str
    command: str
    status: str
    completed_at: datetime | None
    log_sha256: str | None

    @classmethod
    def from_mapping(cls, value: object) -> "VerificationGate":
        if not isinstance(value, Mapping):
            raise PreflightError("gate must be an object")
        _exact_keys(value, _GATE_KEYS, "gate")
        name = _nonempty_string(value["name"], "gate name")
        command = _nonempty_string(value["command"], "gate command")
        status = _nonempty_string(value["status"], "gate status")
        if status not in _STATUSES:
            raise PreflightError("gate status must be passed, failed, or pending")
        completed_raw = value["completedAt"]
        log_sha_raw = value["logSha256"]
        if status == "pending":
            if completed_raw is not None:
                raise PreflightError("pending gate completedAt must be null")
            if log_sha_raw is not None:
                raise PreflightError("pending gate logSha256 must be null")
            completed_at = None
            log_sha256 = None
        else:
            completed_at = _timestamp(completed_raw, "gate completedAt")
            log_sha256 = _nonempty_string(log_sha_raw, "gate logSha256")
            if SHA256_RE.fullmatch(log_sha256) is None:
                raise PreflightError("gate logSha256 must be a lower-case 64-character SHA-256")
        return cls(name=name, command=command, status=status, completed_at=completed_at,
                   log_sha256=log_sha256)

    def to_mapping(self) -> dict[str, object]:
        return {"name": self.name, "command": self.command, "status": self.status,
                "completedAt": _format_timestamp(self.completed_at) if self.completed_at else None,
                "logSha256": self.log_sha256}


_REMOTE_KEYS = frozenset({"sdkVersion", "imageDigest", "requestedTarget", "requestedGpuOrder",
    "sourceCommit", "verificationCommit", "manifestSha256", "workerContextSha256",
    "observedGpu", "sandboxId", "createdAt", "startedAt", "completedAt", "deletedAt",
    "commandResults", "uploads", "downloads", "cleanupAttempts", "deletionConfirmed",
    "runpodMutationOccurred", "registryMutationOccurred"})
_COMMAND_KEYS = frozenset({"command", "exitCode", "stdout", "stderr"})
_IDENTITY_KEYS = frozenset({"name", "sha256", "sizeBytes"})


def _format_timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _safe_text(value: object, label: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value) or len(value) > MAX_JSON_STRING or "\0" in value:
        raise PreflightError(f"{label} must be bounded text")
    if _SECRET_TEXT.search(value):
        raise PreflightError(f"{label} must not contain secret-bearing text")
    return value


@dataclass(frozen=True, slots=True)
class RemoteExecution:
    value: Mapping[str, object]
    timestamps: tuple[datetime, datetime, datetime, datetime]

    @classmethod
    def from_mapping(cls, raw: object) -> "RemoteExecution":
        if not isinstance(raw, Mapping): raise PreflightError("remoteExecution must be an object")
        _exact_keys(raw, _REMOTE_KEYS, "remoteExecution")
        policy = load_daytona_policy()
        exact = {"sdkVersion": policy.sdk_version, "imageDigest": policy.image,
                 "requestedTarget": policy.target, "requestedGpuOrder": list(policy.gpu_types),
                 "deletionConfirmed": True, "runpodMutationOccurred": False,
                 "registryMutationOccurred": False}
        for key, expected in exact.items():
            if type(raw[key]) is not type(expected) or raw[key] != expected:
                raise PreflightError(f"remoteExecution {key} is invalid")
        for key, pattern in (("sourceCommit", SOURCE_COMMIT_RE),
                             ("verificationCommit", SOURCE_COMMIT_RE),
                             ("manifestSha256", SHA256_RE),
                             ("workerContextSha256", SHA256_RE)):
            if pattern.fullmatch(_safe_text(raw[key], f"remoteExecution {key}")) is None:
                raise PreflightError(f"remoteExecution {key} is invalid")
        observed = _safe_text(raw["observedGpu"], "remoteExecution observedGpu")
        if observed not in policy.gpu_types: raise PreflightError("remoteExecution observedGpu is invalid")
        _safe_text(raw["sandboxId"], "remoteExecution sandboxId")
        timestamps = tuple(_timestamp(raw[key], f"remoteExecution {key}") for key in ("createdAt", "startedAt", "completedAt", "deletedAt"))
        if tuple(sorted(timestamps)) != timestamps: raise PreflightError("remoteExecution timestamps must be ordered")
        commands = raw["commandResults"]
        if not isinstance(commands, list) or not 1 <= len(commands) <= 32: raise PreflightError("remoteExecution commandResults must be bounded")
        command_names = []
        for item in commands:
            if not isinstance(item, Mapping): raise PreflightError("remoteExecution command result must be an object")
            _exact_keys(item, _COMMAND_KEYS, "remoteExecution command result")
            command_names.append(_safe_text(item["command"], "remoteExecution command"))
            if type(item["exitCode"]) is not int or item["exitCode"] != 0: raise PreflightError("remoteExecution exitCode must be zero")
            _safe_text(item["stdout"], "remoteExecution stdout", empty=True); _safe_text(item["stderr"], "remoteExecution stderr", empty=True)
        if len(command_names) != len(set(command_names)): raise PreflightError("remoteExecution contains duplicate command results")
        for field in ("uploads", "downloads"):
            identities = raw[field]
            if not isinstance(identities, list) or not 1 <= len(identities) <= 1024: raise PreflightError(f"remoteExecution {field} must be bounded")
            names = []
            for item in identities:
                if not isinstance(item, Mapping): raise PreflightError(f"remoteExecution {field} identity must be an object")
                _exact_keys(item, _IDENTITY_KEYS, f"remoteExecution {field} identity")
                names.append(_safe_text(item["name"], f"remoteExecution {field} name"))
                digest = _safe_text(item["sha256"], f"remoteExecution {field} sha256")
                if SHA256_RE.fullmatch(digest) is None: raise PreflightError(f"remoteExecution {field} sha256 is invalid")
                if isinstance(item["sizeBytes"], bool) or not isinstance(item["sizeBytes"], int) or not 0 <= item["sizeBytes"] <= 1 << 50: raise PreflightError(f"remoteExecution {field} sizeBytes is invalid")
            if len(names) != len(set(names)): raise PreflightError(f"remoteExecution {field} contains duplicate identities")
        attempts = raw["cleanupAttempts"]
        if isinstance(attempts, bool) or not isinstance(attempts, int) or not 1 <= attempts <= policy.cleanup_attempts: raise PreflightError("remoteExecution cleanupAttempts is invalid")
        return cls(dict(raw), timestamps)

    def to_mapping(self) -> dict[str, object]:
        return dict(self.value)


@dataclass(frozen=True, slots=True)
class VerificationEvidence:
    schema_version: int
    phase: str
    source_commit: str
    verification_commit: str
    manifest_sha256: str
    created_at: datetime
    tool_versions: tuple[tuple[str, str], ...]
    gates: tuple[VerificationGate, ...]
    overall_passed: bool
    remote_execution: RemoteExecution | None

    @classmethod
    def from_mapping(cls, value: object) -> "VerificationEvidence":
        if not isinstance(value, Mapping):
            raise PreflightError("verification evidence must be an object")
        _exact_keys(value, _EVIDENCE_KEYS, "verification evidence")
        schema_version = value["schemaVersion"]
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version != SCHEMA_VERSION
        ):
            raise PreflightError(f"schemaVersion must be {SCHEMA_VERSION}")
        phase = _nonempty_string(value["phase"], "phase")
        if phase not in _PHASES:
            raise PreflightError("phase must be pre_cloud or final")
        source_commit = _nonempty_string(value["sourceCommit"], "sourceCommit")
        if SOURCE_COMMIT_RE.fullmatch(source_commit) is None:
            raise PreflightError("sourceCommit must be a lower-case 40-character SHA")
        verification_commit = _nonempty_string(
            value["verificationCommit"], "verificationCommit"
        )
        if SOURCE_COMMIT_RE.fullmatch(verification_commit) is None:
            raise PreflightError("verificationCommit must be a lower-case 40-character SHA")
        manifest_sha256 = _nonempty_string(value["manifestSha256"], "manifestSha256")
        if SHA256_RE.fullmatch(manifest_sha256) is None:
            raise PreflightError("manifestSha256 must be a lower-case 64-character SHA-256")
        tool_versions = value["toolVersions"]
        if (
            not isinstance(tool_versions, Mapping)
            or not tool_versions
            or any(not isinstance(key, str) or not key for key in tool_versions)
            or any(not isinstance(item, str) or not item for item in tool_versions.values())
        ):
            raise PreflightError("toolVersions must be a non-empty string-to-string object")
        raw_gates = value["gates"]
        if not isinstance(raw_gates, list) or not raw_gates:
            raise PreflightError("gates must be a non-empty list")
        gates = tuple(VerificationGate.from_mapping(item) for item in raw_gates)
        names = [gate.name for gate in gates]
        if len(names) != len(set(names)):
            raise PreflightError("duplicate gate name")
        overall_passed = value["overallPassed"]
        if not isinstance(overall_passed, bool):
            raise PreflightError("overallPassed must be a boolean")
        created_at = _timestamp(value["createdAt"], "createdAt")
        remote_raw = value["remoteExecution"]
        remote_execution = None if remote_raw is None else RemoteExecution.from_mapping(remote_raw)
        if remote_execution is not None:
            for key, expected in (("sourceCommit", source_commit),
                                  ("verificationCommit", verification_commit),
                                  ("manifestSha256", manifest_sha256)):
                if remote_execution.value[key] != expected:
                    raise PreflightError(f"remoteExecution {key} does not match evidence")
        for gate in gates:
            if gate.completed_at is not None and gate.completed_at > created_at:
                raise PreflightError(
                    f"gate {gate.name} completedAt must not be after evidence createdAt"
                )
        if remote_execution is not None:
            remote_gate = next((gate for gate in gates if gate.name == REMOTE_GATE_NAME), None)
            if (
                remote_gate is not None
                and remote_gate.completed_at is not None
                and remote_execution.timestamps[-1] != remote_gate.completed_at
            ):
                raise PreflightError(
                    "remoteExecution deletedAt must equal Daytona gate completedAt"
                )
        return cls(
            schema_version=SCHEMA_VERSION,
            phase=phase,
            source_commit=source_commit,
            verification_commit=verification_commit,
            manifest_sha256=manifest_sha256,
            created_at=created_at,
            tool_versions=tuple(sorted(tool_versions.items())),
            gates=gates,
            overall_passed=overall_passed,
            remote_execution=remote_execution,
        )

    def to_mapping(self) -> dict[str, object]:
        return {"schemaVersion": self.schema_version, "phase": self.phase,
                "sourceCommit": self.source_commit, "verificationCommit": self.verification_commit,
                "manifestSha256": self.manifest_sha256,
                "createdAt": _format_timestamp(self.created_at), "toolVersions": dict(self.tool_versions),
                "gates": [gate.to_mapping() for gate in self.gates], "overallPassed": self.overall_passed,
                "remoteExecution": self.remote_execution.to_mapping() if self.remote_execution else None}


def load_verification_evidence(path: Path | str) -> VerificationEvidence:
    source = Path(path)
    try:
        return VerificationEvidence.from_mapping(load_json_mapping(source))
    except (ManifestError, OSError) as exc:
        raise PreflightError(f"verification evidence cannot load from {source}: {exc}") from exc


def validate_evidence_phase(evidence: VerificationEvidence, mode: str) -> None:
    expected_names = tuple(REQUIRED_GATE_COMMANDS)
    actual_names = tuple(gate.name for gate in evidence.gates)
    if actual_names != expected_names:
        raise PreflightError(
            "evidence must use the exact canonical gate inventory in order: "
            + ", ".join(expected_names)
        )
    for gate in evidence.gates:
        expected_command = REQUIRED_GATE_COMMANDS[gate.name]
        if gate.command != expected_command:
            raise PreflightError(
                f"gate {gate.name} must use canonical command: {expected_command}"
            )
    expected_phase = "pre_cloud" if mode == "build-only" else "final"
    if evidence.phase != expected_phase:
        raise PreflightError(
            f"evidence phase mismatch: {mode} requires {expected_phase}, got {evidence.phase}"
        )
    remote_gates = tuple(
        gate for gate in evidence.gates if gate.name == REMOTE_GATE_NAME
    )
    if len(remote_gates) != 1:
        raise PreflightError(f"evidence must contain exactly one {REMOTE_GATE_NAME} gate")
    if mode == "build-only":
        pre_remote_gates = tuple(
            gate for gate in evidence.gates if gate.name != REMOTE_GATE_NAME
        )
        if not pre_remote_gates:
            raise PreflightError("pre_cloud requires at least one pre-cloud gate")
        for gate in pre_remote_gates:
            if gate.status != "passed":
                raise PreflightError(f"pre-cloud gate {gate.name} must be passed")
        if remote_gates[0].status != "pending":
            raise PreflightError("remote gate must be pending for pre_cloud evidence")
        if evidence.overall_passed:
            raise PreflightError("pre_cloud overallPassed must be false")
        if evidence.remote_execution is not None:
            raise PreflightError("pre_cloud remoteExecution must be null")
        return
    if any(gate.status != "passed" for gate in evidence.gates):
        raise PreflightError("final evidence requires every gate passed")
    if not evidence.overall_passed:
        raise PreflightError("final evidence overallPassed must be true")
    if evidence.remote_execution is None:
        raise PreflightError("final remoteExecution must be non-null")


def validate_evidence_freshness(
    evidence: VerificationEvidence,
    now: datetime,
    max_age_seconds: int,
) -> None:
    if now.tzinfo is None or now.utcoffset() is None:
        raise PreflightError("current time must include a timezone")
    age = (now.astimezone(timezone.utc) - evidence.created_at).total_seconds()
    if age < 0:
        raise PreflightError("evidence createdAt is in the future")
    if age > max_age_seconds:
        raise PreflightError(
            f"evidence is stale: age {int(age)} seconds exceeds {max_age_seconds} seconds"
        )
    for gate in evidence.gates:
        if gate.completed_at is None:
            continue
        gate_age = (now.astimezone(timezone.utc) - gate.completed_at).total_seconds()
        if gate_age > max_age_seconds:
            raise PreflightError(
                f"gate {gate.name} is stale: age {int(gate_age)} seconds exceeds "
                f"{max_age_seconds} seconds"
            )
    if evidence.remote_execution is not None:
        for label, timestamp in zip(
            ("createdAt", "startedAt", "completedAt", "deletedAt"),
            evidence.remote_execution.timestamps,
            strict=True,
        ):
            remote_age = (now.astimezone(timezone.utc) - timestamp).total_seconds()
            if remote_age < 0:
                raise PreflightError(f"remoteExecution {label} is in the future")
            if remote_age > max_age_seconds:
                raise PreflightError(
                    f"remoteExecution {label} is stale: age {int(remote_age)} seconds "
                    f"exceeds {max_age_seconds} seconds"
                )


def validate_evidence_validity_window(
    evidence: VerificationEvidence,
    now: datetime,
    max_age_seconds: int,
    minimum_validity_seconds: int,
) -> int:
    if isinstance(minimum_validity_seconds, bool) or minimum_validity_seconds < 0:
        raise PreflightError("minimum evidence validity must be a non-negative integer")
    validate_evidence_freshness(evidence, now, max_age_seconds)
    timestamps = [evidence.created_at]
    timestamps.extend(gate.completed_at for gate in evidence.gates if gate.completed_at is not None)
    if evidence.remote_execution is not None:
        timestamps.extend(evidence.remote_execution.timestamps)
    valid_until = min(timestamps) + timedelta(seconds=max_age_seconds)
    remaining = max(0, int((valid_until - now.astimezone(timezone.utc)).total_seconds()))
    if remaining < minimum_validity_seconds:
        raise PreflightError(
            f"evidence expires too soon: {remaining} seconds remain, "
            f"need {minimum_validity_seconds} seconds"
        )
    return remaining
