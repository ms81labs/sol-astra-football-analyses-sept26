"""Strict, portable release-manifest values and artifact resolution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
from types import MappingProxyType
from typing import Any, Mapping


SCHEMA_VERSION = 1
KNOWN_REQUIRED_CONTRACTS = frozenset(
    {
        "video_to_analysis_product_api_v1",
        "video_to_analysis_report_v1",
    }
)

_MANIFEST_KEYS = frozenset(
    {
        "schemaVersion",
        "releaseVersion",
        "candidateVersion",
        "runtimeVersion",
        "sourceCommit",
        "createdAt",
        "runtimeOptions",
        "artifacts",
        "requiredContracts",
    }
)
_ARTIFACT_KEYS = frozenset(
    {
        "id",
        "sha256",
        "sizeBytes",
        "localRelativePath",
        "containerPath",
        "origin",
        "retentionClass",
    }
)
_VERSION = re.compile(
    r"^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    r"(?:\.(?:0|[1-9][0-9]*))?(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?$"
)
_SOURCE_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_RFC3339 = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,9})?(?:Z|[+-][0-9]{2}:[0-9]{2})$"
)
_CONTAINER_PREFIXES = ("/app/models/", "/app/release-inputs/")


class ManifestError(ValueError):
    """Raised when release data or a resolved artifact is unsafe or invalid."""


def _exact_keys(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    if any(not isinstance(key, str) for key in value):
        raise ManifestError(f"{label} object keys must be strings")
    keys = set(value)
    missing = sorted(expected - keys)
    unknown = sorted(keys - expected)
    if missing:
        raise ManifestError(f"{label} missing keys: {', '.join(missing)}")
    if unknown:
        raise ManifestError(f"{label} unknown keys: {', '.join(unknown)}")


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{label} must be a non-empty string")
    return value


def _version(value: object, label: str) -> str:
    result = _string(value, label)
    if _VERSION.fullmatch(result) is None:
        raise ManifestError(f"{label} must be a v-prefixed release version")
    return result


def _timestamp(value: object) -> str:
    result = _string(value, "createdAt")
    if _RFC3339.fullmatch(result) is None:
        raise ManifestError("createdAt must be an RFC3339 timestamp with timezone")
    try:
        parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ManifestError("createdAt must be a valid RFC3339 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ManifestError("createdAt must include an RFC3339 timezone")
    return result


def _safe_local_path(value: object) -> str:
    result = _string(value, "localRelativePath")
    if "\0" in result or "\\" in result or result.startswith(("/", "~")):
        raise ManifestError("localRelativePath must be a safe relative POSIX path")
    raw_parts = result.split("/")
    candidate = PurePosixPath(result)
    if (
        any(part in {"", ".", ".."} for part in raw_parts)
        or raw_parts[0].endswith(":")
        or candidate.is_absolute()
        or candidate.as_posix() != result
    ):
        raise ManifestError("localRelativePath must be a safe relative POSIX path")
    return result


def _safe_container_path(value: object) -> str:
    result = _string(value, "containerPath")
    if "\0" in result or "\\" in result or not result.startswith(_CONTAINER_PREFIXES):
        raise ManifestError("containerPath must be under /app/models/ or /app/release-inputs/")
    raw_parts = result[1:].split("/")
    candidate = PurePosixPath(result)
    if any(part in {"", ".", ".."} for part in raw_parts) or candidate.as_posix() != result:
        raise ManifestError("containerPath must be a normalized portable container path")
    return result


def _looks_like_host_path(value: str) -> bool:
    return (
        value.startswith(("/", "~/", "file://"))
        or re.match(r"^[A-Za-z]:[\\/]", value) is not None
    )


def _portable_identifier(value: object, label: str) -> str:
    """Validate metadata labels that must never carry paths or free-form prose."""

    result = _string(value, label)
    if _IDENTIFIER.fullmatch(result) is None:
        raise ManifestError(f"{label} must be a lower-case portable identifier")
    return result


def _freeze_json(value: object, label: str) -> object:
    if isinstance(value, str):
        if _looks_like_host_path(value):
            raise ManifestError(f"{label} must not contain an absolute host path")
        return value
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ManifestError(f"{label} must contain only finite JSON values")
        return value
    if isinstance(value, list):
        return tuple(_freeze_json(item, label) for item in value)
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ManifestError(f"{label} object keys must be strings")
        if any(_looks_like_host_path(key) for key in value):
            raise ManifestError(f"{label} must not contain an absolute host path in object keys")
        return MappingProxyType({key: _freeze_json(item, label) for key, item in value.items()})
    raise ManifestError(f"{label} must contain only JSON values")


def _thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json_mapping(path: Path | str) -> dict[str, Any]:
    """Load a UTF-8 JSON object while rejecting duplicate object keys."""

    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"), object_pairs_hook=_json_pairs)
    except ManifestError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot load JSON from {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise ManifestError(f"JSON at {source} must be an object")
    return value


@dataclass(frozen=True, slots=True)
class Artifact:
    id: str
    sha256: str
    size_bytes: int
    local_relative_path: str
    container_path: str
    origin: str
    retention_class: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Artifact":
        if not isinstance(value, Mapping):
            raise ManifestError("artifact must be an object")
        _exact_keys(value, _ARTIFACT_KEYS, "artifact")
        artifact_id = _string(value["id"], "artifact id")
        if _IDENTIFIER.fullmatch(artifact_id) is None:
            raise ManifestError("artifact id must be a lower-case portable identifier")
        digest = _string(value["sha256"], "sha256")
        if _SHA256.fullmatch(digest) is None:
            raise ManifestError("sha256 must be a lower-case 64-character hexadecimal digest")
        size = value["sizeBytes"]
        if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            raise ManifestError("sizeBytes must be a positive integer")
        return cls(
            id=artifact_id,
            sha256=digest,
            size_bytes=size,
            local_relative_path=_safe_local_path(value["localRelativePath"]),
            container_path=_safe_container_path(value["containerPath"]),
            origin=_portable_identifier(value["origin"], "origin"),
            retention_class=_portable_identifier(value["retentionClass"], "retentionClass"),
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "id": self.id,
            "sha256": self.sha256,
            "sizeBytes": self.size_bytes,
            "localRelativePath": self.local_relative_path,
            "containerPath": self.container_path,
            "origin": self.origin,
            "retentionClass": self.retention_class,
        }


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    schema_version: int
    release_version: str
    candidate_version: str
    runtime_version: str
    source_commit: str
    created_at: str
    runtime_options: Mapping[str, object]
    artifacts: tuple[Artifact, ...]
    required_contracts: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ReleaseManifest":
        if not isinstance(value, Mapping):
            raise ManifestError("release manifest must be an object")
        _exact_keys(value, _MANIFEST_KEYS, "release manifest")
        schema = value["schemaVersion"]
        if isinstance(schema, bool) or not isinstance(schema, int) or schema != SCHEMA_VERSION:
            raise ManifestError(f"schemaVersion must be {SCHEMA_VERSION}")
        source_commit = _string(value["sourceCommit"], "sourceCommit")
        if _SOURCE_COMMIT.fullmatch(source_commit) is None:
            raise ManifestError("sourceCommit must be a lower-case 40-character hexadecimal SHA")
        release_version = _version(value["releaseVersion"], "releaseVersion")
        candidate_version = _version(value["candidateVersion"], "candidateVersion")
        runtime_version = _version(value["runtimeVersion"], "runtimeVersion")
        if not (
            release_version == candidate_version == runtime_version == "v7.3"
        ):
            raise ManifestError(
                "releaseVersion, candidateVersion, and runtimeVersion must all be v7.3"
            )
        runtime_options = value["runtimeOptions"]
        if not isinstance(runtime_options, Mapping):
            raise ManifestError("runtimeOptions must be an object")
        frozen_options = _freeze_json(runtime_options, "runtimeOptions")
        if not isinstance(frozen_options, Mapping):  # pragma: no cover - guarded above
            raise ManifestError("runtimeOptions must be an object")
        raw_artifacts = value["artifacts"]
        if not isinstance(raw_artifacts, list):
            raise ManifestError("artifacts must be a list")
        artifacts = tuple(Artifact.from_mapping(item) for item in raw_artifacts)
        if not artifacts:
            raise ManifestError("artifacts must contain at least one artifact")
        cls._reject_duplicate_artifact_fields(artifacts)
        try:
            from .runtime_options import ProofRuntimeOptions, RuntimeOptionsError

            typed_runtime_options = ProofRuntimeOptions.from_mapping(runtime_options)
        except RuntimeOptionsError as exc:
            raise ManifestError(f"runtimeOptions contract is invalid: {exc}") from exc
        declared_artifact_ids = {artifact.id for artifact in artifacts}
        for field in (
            "primary_model",
            "auxiliary_ball_model",
            "baseline_guided_rescue_reference",
            "proposal_selection_truth_seed",
            "reviewed_positive_anchor_seed",
        ):
            reference = getattr(typed_runtime_options, field)
            if (
                reference is not None
                and reference.kind == "artifact"
                and reference.artifact_id not in declared_artifact_ids
            ):
                raise ManifestError(
                    f"runtimeOptions {field} references undeclared artifact: "
                    f"{reference.artifact_id}"
                )
        raw_contracts = value["requiredContracts"]
        if not isinstance(raw_contracts, list) or not raw_contracts:
            raise ManifestError("requiredContracts must be a non-empty list")
        if any(not isinstance(item, str) for item in raw_contracts):
            raise ManifestError("requiredContracts entries must be strings")
        contracts = tuple(raw_contracts)
        if len(contracts) != len(set(contracts)):
            raise ManifestError("requiredContracts must not contain duplicates")
        unknown_contracts = sorted(set(contracts) - KNOWN_REQUIRED_CONTRACTS)
        if unknown_contracts:
            raise ManifestError(f"unknown required contract: {', '.join(unknown_contracts)}")
        if set(contracts) != KNOWN_REQUIRED_CONTRACTS:
            raise ManifestError(
                "requiredContracts must contain exactly "
                "video_to_analysis_product_api_v1 and video_to_analysis_report_v1"
            )
        return cls(
            schema_version=schema,
            release_version=release_version,
            candidate_version=candidate_version,
            runtime_version=runtime_version,
            source_commit=source_commit,
            created_at=_timestamp(value["createdAt"]),
            runtime_options=frozen_options,
            artifacts=artifacts,
            required_contracts=contracts,
        )

    @staticmethod
    def _reject_duplicate_artifact_fields(artifacts: tuple[Artifact, ...]) -> None:
        for attribute, label in (
            ("id", "id"),
            ("local_relative_path", "localRelativePath"),
            ("container_path", "containerPath"),
        ):
            values = [getattr(artifact, attribute) for artifact in artifacts]
            if len(values) != len(set(values)):
                raise ManifestError(f"duplicate artifact {label}")

    def to_mapping(self) -> dict[str, object]:
        return {
            "schemaVersion": self.schema_version,
            "releaseVersion": self.release_version,
            "candidateVersion": self.candidate_version,
            "runtimeVersion": self.runtime_version,
            "sourceCommit": self.source_commit,
            "createdAt": self.created_at,
            "runtimeOptions": _thaw_json(self.runtime_options),
            "artifacts": [artifact.to_mapping() for artifact in self.artifacts],
            "requiredContracts": list(self.required_contracts),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_mapping(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    def validate_source_commit(self, expected_source_commit: str) -> None:
        if not isinstance(expected_source_commit, str) or _SOURCE_COMMIT.fullmatch(expected_source_commit) is None:
            raise ManifestError("expected source commit must be a lower-case 40-character hexadecimal SHA")
        if self.source_commit != expected_source_commit:
            raise ManifestError(
                f"source commit mismatch: manifest has {self.source_commit}, expected {expected_source_commit}"
            )


def load_release_manifest(path: Path | str, *, expected_source_commit: str | None = None) -> ReleaseManifest:
    manifest = ReleaseManifest.from_mapping(load_json_mapping(path))
    if expected_source_commit is not None:
        manifest.validate_source_commit(expected_source_commit)
    return manifest


def _resolver_root(root: Path | str) -> Path:
    candidate = Path(root)
    if not candidate.is_absolute():
        raise ManifestError("artifact resolver root must be absolute")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ManifestError(f"artifact resolver root does not exist: {candidate}") from exc
    if not resolved.is_dir():
        raise ManifestError(f"artifact resolver root is not a directory: {resolved}")
    return resolved


def _stream_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_artifact(
    manifest: ReleaseManifest,
    artifact_id: str,
    root: Path | str,
    environment: str,
) -> Path:
    """Resolve one artifact below an explicit root and verify size and SHA-256."""

    if environment not in {"local", "container"}:
        raise ManifestError(f"unknown environment: {environment}")
    artifact = next((item for item in manifest.artifacts if item.id == artifact_id), None)
    if artifact is None:
        raise ManifestError(f"unknown artifact: {artifact_id}")
    resolved_root = _resolver_root(root)
    declared_path = (
        artifact.local_relative_path
        if environment == "local"
        else artifact.container_path.removeprefix("/")
    )
    candidate = resolved_root.joinpath(*PurePosixPath(declared_path).parts)
    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        raise ManifestError(f"cannot resolve artifact {artifact.id}: {exc}") from exc
    if not resolved.is_relative_to(resolved_root):
        raise ManifestError(f"artifact {artifact.id} escapes resolver root")
    if not resolved.is_file():
        raise ManifestError(
            f"missing artifact {artifact.id} at {resolved}; expected sha256 {artifact.sha256}"
        )
    actual_size = resolved.stat().st_size
    if actual_size != artifact.size_bytes:
        raise ManifestError(
            f"artifact {artifact.id} at {resolved} size mismatch: "
            f"expected {artifact.size_bytes}, got {actual_size}; expected sha256 {artifact.sha256}"
        )
    actual_hash = _stream_sha256(resolved)
    if actual_hash != artifact.sha256:
        raise ManifestError(
            f"artifact {artifact.id} at {resolved} sha256 mismatch: "
            f"expected {artifact.sha256}, got {actual_hash}"
        )
    return resolved
