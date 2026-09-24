"""Portable, fail-closed proof runtime options and artifact references."""

from __future__ import annotations

import logging

import base64
from collections.abc import Iterable
from dataclasses import dataclass
import hashlib
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from typing import TYPE_CHECKING, Any, BinaryIO, Callable, Mapping


LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .release_manifest import ReleaseManifest


_OPTION_FIELDS = (
    "primary_model",
    "auxiliary_ball_model",
    "auxiliary_ball_model_profile",
    "primary_acquisition_mode",
    "edge_share_repair_profile",
    "baseline_guided_rescue_reference",
    "proposal_selection_truth_seed",
    "reviewed_positive_anchor_seed",
)
_OPTION_FIELD_SET = frozenset(_OPTION_FIELDS)
_REFERENCE_VARIANTS = frozenset({"artifactId", "objectStore", "inline"})
_OBJECT_STORE_FIELDS = frozenset(
    {"bucket", "key", "endpointUrl", "region", "sha256", "sizeBytes"}
)
_INLINE_FIELDS = frozenset({"name", "contentBase64", "sha256", "sizeBytes"})
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PORTABLE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_BASE64 = re.compile(r"^[A-Za-z0-9+/]*={0,2}$")
_DNS_HOSTNAME = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*$"
)

HARD_MAX_RUNTIME_ARTIFACT_BYTES = 128 * 1024 * 1024
OBJECT_STORE_ALLOWED_ORIGINS_ENV = "PROOF_RUNTIME_OBJECT_STORE_ALLOWED_ORIGINS"
RUNTIME_ARTIFACT_MAX_BYTES_ENV = "PROOF_RUNTIME_MAX_ARTIFACT_BYTES"


class RuntimeOptionsError(ValueError):
    """Raised when a runtime option or materialized reference is unsafe."""


def _exact_keys(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    if any(not isinstance(key, str) for key in value):
        raise RuntimeOptionsError(f"{label} object keys must be strings")
    missing = sorted(expected - set(value))
    unknown = sorted(set(value) - expected)
    if missing:
        raise RuntimeOptionsError(f"{label} missing fields: {', '.join(missing)}")
    if unknown:
        raise RuntimeOptionsError(f"{label} unknown fields: {', '.join(unknown)}")


def _non_empty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeOptionsError(f"{label} must be a non-empty string")
    return value.strip()


def _optional_string(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _non_empty_string(value, label)


def _positive_size(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise RuntimeOptionsError(f"{label} must be a positive integer")
    if value > HARD_MAX_RUNTIME_ARTIFACT_BYTES:
        raise RuntimeOptionsError(
            f"{label} exceeds the hard safe maximum of {HARD_MAX_RUNTIME_ARTIFACT_BYTES} bytes"
        )
    return value


def _digest(value: object, label: str) -> str:
    digest = _non_empty_string(value, label)
    if _SHA256.fullmatch(digest) is None:
        raise RuntimeOptionsError(f"{label} must be a lower-case SHA-256 digest")
    return digest


def _safe_relative_path(value: object, label: str, *, basename_only: bool = False) -> str:
    result = _non_empty_string(value, label)
    if "\0" in result or "\\" in result or result.startswith(("/", "~", "file://")):
        raise RuntimeOptionsError(f"{label} must be a safe relative POSIX path")
    parts = result.split("/")
    candidate = PurePosixPath(result)
    if (
        any(part in {"", ".", ".."} for part in parts)
        or candidate.is_absolute()
        or candidate.as_posix() != result
        or re.match(r"^[A-Za-z]:", parts[0]) is not None
        or (basename_only and len(parts) != 1)
    ):
        raise RuntimeOptionsError(f"{label} must be a safe relative POSIX path")
    return result


def normalize_object_store_origin(value: object, label: str = "objectStore.endpointUrl") -> str:
    from urllib.parse import urlparse

    endpoint_url = _non_empty_string(value, label)
    parsed = urlparse(endpoint_url)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeOptionsError(f"{label} must be a clean HTTPS origin")
    try:
        port = parsed.port
    except ValueError as exc:
        raise RuntimeOptionsError(f"{label} must contain a valid port") from exc
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise RuntimeOptionsError(f"{label} must not target localhost")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
        if _DNS_HOSTNAME.fullmatch(hostname) is None:
            raise RuntimeOptionsError(f"{label} must contain a valid hostname") from None
    if address is not None and not address.is_global:
        raise RuntimeOptionsError(f"{label} must not target a non-public IP address")
    rendered_host = f"[{hostname}]" if ":" in hostname else hostname
    if port is not None and port != 443:
        rendered_host = f"{rendered_host}:{port}"
    return f"https://{rendered_host}"


def configured_object_store_allowed_origins() -> frozenset[str]:
    """Return exact normalized origins explicitly configured by the operator.

    ``PROOF_RUNTIME_OBJECT_STORE_ALLOWED_ORIGINS`` is a comma-separated origin
    allowlist.
    """

    configured: list[str] = []
    raw_allowlist = os.environ.get(OBJECT_STORE_ALLOWED_ORIGINS_ENV, "")
    configured.extend(item.strip() for item in raw_allowlist.split(",") if item.strip())
    return frozenset(
        normalize_object_store_origin(origin, f"configured origin in {OBJECT_STORE_ALLOWED_ORIGINS_ENV}")
        for origin in configured
    )


def configured_runtime_artifact_max_bytes() -> int:
    raw_value = os.environ.get(RUNTIME_ARTIFACT_MAX_BYTES_ENV)
    if raw_value is None or not raw_value.strip():
        return HARD_MAX_RUNTIME_ARTIFACT_BYTES
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeOptionsError(f"{RUNTIME_ARTIFACT_MAX_BYTES_ENV} must be a positive integer") from exc
    if value <= 0 or value > HARD_MAX_RUNTIME_ARTIFACT_BYTES:
        raise RuntimeOptionsError(
            f"{RUNTIME_ARTIFACT_MAX_BYTES_ENV} must be between 1 and {HARD_MAX_RUNTIME_ARTIFACT_BYTES}"
        )
    return value


def _validate_base64_declared_length(content_base64: str, declared_size: int) -> None:
    try:
        content_base64.encode("ascii")
    except UnicodeEncodeError as exc:
        raise RuntimeOptionsError("inline.contentBase64 must be valid base64") from exc
    if (
        len(content_base64) % 4 != 0
        or _BASE64.fullmatch(content_base64) is None
        or "=" in content_base64[:-2]
    ):
        raise RuntimeOptionsError("inline.contentBase64 must be valid base64")
    padding = len(content_base64) - len(content_base64.rstrip("="))
    decoded_length = (len(content_base64) // 4) * 3 - padding
    if decoded_length != declared_size:
        raise RuntimeOptionsError(
            "inline.contentBase64 decoded length does not match inline.sizeBytes"
        )


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    """Exactly one artifact-ID, object-store, or inline content descriptor."""

    kind: str
    artifact_id: str | None = None
    bucket: str | None = None
    key: str | None = None
    endpoint_url: str | None = None
    region: str | None = None
    name: str | None = None
    content_base64: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ArtifactReference":
        if not isinstance(value, Mapping):
            raise RuntimeOptionsError("artifact reference must be an object")
        if any(not isinstance(key, str) for key in value):
            raise RuntimeOptionsError("artifact reference object keys must be strings")
        unknown = sorted(set(value) - _REFERENCE_VARIANTS)
        if unknown:
            raise RuntimeOptionsError(f"artifact reference unknown fields: {', '.join(unknown)}")
        if len(value) != 1:
            raise RuntimeOptionsError("artifact reference must contain exactly one descriptor")
        if "artifactId" in value:
            artifact_id = _non_empty_string(value["artifactId"], "artifactId")
            if _IDENTIFIER.fullmatch(artifact_id) is None:
                raise RuntimeOptionsError("artifactId must be a lower-case portable identifier")
            return cls(kind="artifact", artifact_id=artifact_id)
        if "objectStore" in value:
            descriptor = value["objectStore"]
            if not isinstance(descriptor, Mapping):
                raise RuntimeOptionsError("objectStore must be an object")
            _exact_keys(descriptor, _OBJECT_STORE_FIELDS, "objectStore")
            endpoint_url = normalize_object_store_origin(descriptor["endpointUrl"])
            bucket = _non_empty_string(descriptor["bucket"], "objectStore.bucket")
            region = _non_empty_string(descriptor["region"], "objectStore.region")
            if _PORTABLE_LABEL.fullmatch(bucket) is None or _PORTABLE_LABEL.fullmatch(region) is None:
                raise RuntimeOptionsError("objectStore bucket and region must be portable labels")
            return cls(
                kind="object_store",
                bucket=bucket,
                key=_safe_relative_path(descriptor["key"], "objectStore.key"),
                endpoint_url=endpoint_url,
                region=region,
                sha256=_digest(descriptor["sha256"], "objectStore.sha256"),
                size_bytes=_positive_size(descriptor["sizeBytes"], "objectStore.sizeBytes"),
            )
        descriptor = value.get("inline")
        if not isinstance(descriptor, Mapping):
            raise RuntimeOptionsError("inline must be an object")
        _exact_keys(descriptor, _INLINE_FIELDS, "inline")
        content_base64 = _non_empty_string(descriptor["contentBase64"], "inline.contentBase64")
        size_bytes = _positive_size(descriptor["sizeBytes"], "inline.sizeBytes")
        _validate_base64_declared_length(content_base64, size_bytes)
        return cls(
            kind="inline",
            name=_safe_relative_path(descriptor["name"], "inline.name", basename_only=True),
            content_base64=content_base64,
            sha256=_digest(descriptor["sha256"], "inline.sha256"),
            size_bytes=size_bytes,
        )

    def to_mapping(self) -> dict[str, object]:
        if self.kind == "artifact":
            return {"artifactId": self.artifact_id}
        if self.kind == "object_store":
            return {
                "objectStore": {
                    "bucket": self.bucket,
                    "key": self.key,
                    "endpointUrl": self.endpoint_url,
                    "region": self.region,
                    "sha256": self.sha256,
                    "sizeBytes": self.size_bytes,
                }
            }
        if self.kind == "inline":
            return {
                "inline": {
                    "name": self.name,
                    "contentBase64": self.content_base64,
                    "sha256": self.sha256,
                    "sizeBytes": self.size_bytes,
                }
            }
        raise RuntimeOptionsError(f"unknown artifact reference kind: {self.kind}")

    def to_provenance_mapping(self) -> dict[str, object]:
        if self.kind != "inline":
            return self.to_mapping()
        return {
            "inline": {
                "name": self.name,
                "sha256": self.sha256,
                "sizeBytes": self.size_bytes,
            }
        }


SUPPORTED_PRIMARY_ACQUISITION_MODE = "anchored_player_ranked_context_960"


def validate_primary_acquisition_mode(value: str) -> str:
    if value != SUPPORTED_PRIMARY_ACQUISITION_MODE:
        raise RuntimeOptionsError(f"Unsupported primary acquisition mode: {value}")
    return value


@dataclass(frozen=True, slots=True)
class ProofRuntimeOptions:
    primary_model: ArtifactReference
    auxiliary_ball_model: ArtifactReference | None
    auxiliary_ball_model_profile: str | None
    primary_acquisition_mode: str
    edge_share_repair_profile: str | None
    baseline_guided_rescue_reference: ArtifactReference | None
    proposal_selection_truth_seed: ArtifactReference | None
    reviewed_positive_anchor_seed: ArtifactReference | None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ProofRuntimeOptions":
        if not isinstance(value, Mapping):
            raise RuntimeOptionsError("runtime options must be an object")
        _exact_keys(value, _OPTION_FIELD_SET, "runtime options")

        def reference(field: str, *, required: bool = False) -> ArtifactReference | None:
            raw = value[field]
            if raw is None and not required:
                return None
            if not isinstance(raw, Mapping):
                raise RuntimeOptionsError(f"{field} must be an artifact reference object")
            try:
                return ArtifactReference.from_mapping(raw)
            except RuntimeOptionsError as exc:
                raise RuntimeOptionsError(f"{field}: {exc}") from exc

        primary_model = reference("primary_model", required=True)
        assert primary_model is not None
        return cls(
            primary_model=primary_model,
            auxiliary_ball_model=reference("auxiliary_ball_model"),
            auxiliary_ball_model_profile=_optional_string(
                value["auxiliary_ball_model_profile"], "auxiliary_ball_model_profile"
            ),
            primary_acquisition_mode=_non_empty_string(
                value["primary_acquisition_mode"], "primary_acquisition_mode"
            ),
            edge_share_repair_profile=_optional_string(
                value["edge_share_repair_profile"], "edge_share_repair_profile"
            ),
            baseline_guided_rescue_reference=reference("baseline_guided_rescue_reference"),
            proposal_selection_truth_seed=reference("proposal_selection_truth_seed"),
            reviewed_positive_anchor_seed=reference("reviewed_positive_anchor_seed"),
        )

    @classmethod
    def from_json(cls, payload: str) -> "ProofRuntimeOptions":
        try:
            value = json.loads(payload)
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeOptionsError(f"runtime options JSON is invalid: {exc}") from exc
        if not isinstance(value, dict):
            raise RuntimeOptionsError("runtime options JSON must contain an object")
        return cls.from_mapping(value)

    @classmethod
    def defaults(cls) -> "ProofRuntimeOptions":
        return cls.from_mapping(
            {
                "primary_model": {"artifactId": "primary-model"},
                "auxiliary_ball_model": None,
                "auxiliary_ball_model_profile": None,
                "primary_acquisition_mode": "anchored_player_ranked_context_960",
                "edge_share_repair_profile": None,
                "baseline_guided_rescue_reference": None,
                "proposal_selection_truth_seed": None,
                "reviewed_positive_anchor_seed": None,
            }
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "primary_model": self.primary_model.to_mapping(),
            "auxiliary_ball_model": (
                self.auxiliary_ball_model.to_mapping() if self.auxiliary_ball_model is not None else None
            ),
            "auxiliary_ball_model_profile": self.auxiliary_ball_model_profile,
            "primary_acquisition_mode": self.primary_acquisition_mode,
            "edge_share_repair_profile": self.edge_share_repair_profile,
            "baseline_guided_rescue_reference": (
                self.baseline_guided_rescue_reference.to_mapping()
                if self.baseline_guided_rescue_reference is not None
                else None
            ),
            "proposal_selection_truth_seed": (
                self.proposal_selection_truth_seed.to_mapping()
                if self.proposal_selection_truth_seed is not None
                else None
            ),
            "reviewed_positive_anchor_seed": (
                self.reviewed_positive_anchor_seed.to_mapping()
                if self.reviewed_positive_anchor_seed is not None
                else None
            ),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_mapping(), ensure_ascii=False, sort_keys=True)

    def to_provenance_mapping(self) -> dict[str, object]:
        def reference(value: ArtifactReference | None) -> dict[str, object] | None:
            return value.to_provenance_mapping() if value is not None else None

        return {
            "primary_model": reference(self.primary_model),
            "auxiliary_ball_model": reference(self.auxiliary_ball_model),
            "auxiliary_ball_model_profile": self.auxiliary_ball_model_profile,
            "primary_acquisition_mode": self.primary_acquisition_mode,
            "edge_share_repair_profile": self.edge_share_repair_profile,
            "baseline_guided_rescue_reference": reference(self.baseline_guided_rescue_reference),
            "proposal_selection_truth_seed": reference(self.proposal_selection_truth_seed),
            "reviewed_positive_anchor_seed": reference(self.reviewed_positive_anchor_seed),
        }

_LEGACY_RUNTIME_PATH_FIELDS = frozenset(
    {
        "primaryModelPath",
        "auxiliaryBallModelPath",
        "auxiliaryBallModelProfile",
        "primaryAcquisitionMode",
        "edgeShareRepairProfile",
        "baselineGuidedRescueReferencePath",
        "proposalSelectionTruthSeedPath",
        "reviewedPositiveAnchorSeedPath",
    }
)


def proof_runtime_options_from_http_payload(
    payload: Mapping[str, Any],
    *,
    default_options: ProofRuntimeOptions | None = None,
) -> tuple[ProofRuntimeOptions, tuple[str, ...]]:
    """Parse the HTTP contract, translating only the documented modelPath alias."""

    if not isinstance(payload, Mapping):
        raise RuntimeOptionsError("remote input must be an object")
    forbidden = sorted(field for field in _LEGACY_RUNTIME_PATH_FIELDS if field in payload)
    if forbidden:
        raise RuntimeOptionsError(f"legacy runtime path fields are forbidden: {', '.join(forbidden)}")
    runtime_options_present = "runtimeOptions" in payload
    raw_options = payload.get("runtimeOptions")
    model_alias_present = "modelPath" in payload
    if runtime_options_present:
        if model_alias_present:
            raise RuntimeOptionsError("modelPath cannot be combined with runtimeOptions")
        if not isinstance(raw_options, Mapping):
            raise RuntimeOptionsError("runtimeOptions must be an object")
        return ProofRuntimeOptions.from_mapping(raw_options), ()
    if not model_alias_present:
        if default_options is None:
            raise RuntimeOptionsError(
                "validated release manifest defaults are required when runtimeOptions are absent"
            )
        return default_options, ()
    model_alias = _non_empty_string(payload.get("modelPath"), "modelPath")
    if _IDENTIFIER.fullmatch(model_alias) is None:
        raise RuntimeOptionsError("modelPath compatibility alias must be a portable artifact identifier")
    defaults = default_options or ProofRuntimeOptions.defaults()
    return (
        ProofRuntimeOptions(
            primary_model=ArtifactReference(kind="artifact", artifact_id=model_alias),
            auxiliary_ball_model=defaults.auxiliary_ball_model,
            auxiliary_ball_model_profile=defaults.auxiliary_ball_model_profile,
            primary_acquisition_mode=defaults.primary_acquisition_mode,
            edge_share_repair_profile=defaults.edge_share_repair_profile,
            baseline_guided_rescue_reference=defaults.baseline_guided_rescue_reference,
            proposal_selection_truth_seed=defaults.proposal_selection_truth_seed,
            reviewed_positive_anchor_seed=defaults.reviewed_positive_anchor_seed,
        ),
        ("modelPath",),
    )


ObjectStream = Iterable[bytes] | BinaryIO
ObjectLoader = Callable[[ArtifactReference], ObjectStream]


def _verify_materialized(path: Path, reference: ArtifactReference) -> Path:
    if not path.is_file():
        raise RuntimeOptionsError(f"materialized {reference.kind} reference is unavailable at {path}")
    assert reference.size_bytes is not None
    assert reference.sha256 is not None
    try:
        actual_size = path.stat().st_size
    except OSError as exc:
        raise RuntimeOptionsError(f"materialized reference is not readable: {path}") from exc
    if actual_size != reference.size_bytes:
        raise RuntimeOptionsError(
            f"materialized {reference.kind} reference size mismatch: expected {reference.size_bytes}, got {actual_size}"
        )
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    actual_digest = digest.hexdigest()
    if actual_digest != reference.sha256:
        raise RuntimeOptionsError(
            f"materialized {reference.kind} reference sha256 mismatch: expected {reference.sha256}, got {actual_digest}"
        )
    try:
        with path.open("rb") as stream:
            stream.read(1)
    except OSError as exc:
        raise RuntimeOptionsError(f"materialized reference is not readable: {path}") from exc
    return path


def _effective_max_artifact_bytes(value: int | None) -> int:
    if value is None:
        return configured_runtime_artifact_max_bytes()
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise RuntimeOptionsError("max_artifact_bytes must be a positive integer")
    if value > HARD_MAX_RUNTIME_ARTIFACT_BYTES:
        raise RuntimeOptionsError(
            f"max_artifact_bytes cannot exceed {HARD_MAX_RUNTIME_ARTIFACT_BYTES}"
        )
    return value


def _iter_stream_chunks(stream: ObjectStream) -> Iterable[bytes]:
    read = getattr(stream, "read", None)
    if callable(read):
        while True:
            chunk = read(1024 * 1024)
            if not chunk:
                return
            yield chunk
    else:
        yield from stream


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_materialize(
    reference: ArtifactReference,
    destination: Path,
    chunks: ObjectStream,
    *,
    max_artifact_bytes: int,
) -> Path:
    assert reference.size_bytes is not None
    assert reference.sha256 is not None
    if reference.size_bytes > max_artifact_bytes:
        raise RuntimeOptionsError(
            f"runtime artifact declared size {reference.size_bytes} exceeds configured maximum "
            f"of {max_artifact_bytes} bytes"
        )
    temporary_path: Path | None = None
    installed = False
    stream_close = getattr(chunks, "close", None)
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            os.chmod(temporary_path, 0o600)
            digest = hashlib.sha256()
            written = 0
            for chunk in _iter_stream_chunks(chunks):
                if not isinstance(chunk, (bytes, bytearray, memoryview)):
                    raise RuntimeOptionsError("object loader chunks must be bytes")
                chunk_bytes = bytes(chunk)
                if not chunk_bytes:
                    continue
                next_size = written + len(chunk_bytes)
                if next_size > reference.size_bytes:
                    raise RuntimeOptionsError(
                        "materialized object_store reference exceeds declared size"
                    )
                if next_size > max_artifact_bytes:
                    raise RuntimeOptionsError(
                        "materialized object_store reference exceeds configured maximum"
                    )
                temporary.write(chunk_bytes)
                digest.update(chunk_bytes)
                written = next_size
            if written != reference.size_bytes:
                raise RuntimeOptionsError(
                    f"materialized {reference.kind} reference size mismatch: "
                    f"expected {reference.size_bytes}, got {written}"
                )
            actual_digest = digest.hexdigest()
            if actual_digest != reference.sha256:
                raise RuntimeOptionsError(
                    f"materialized {reference.kind} reference sha256 mismatch: "
                    f"expected {reference.sha256}, got {actual_digest}"
                )
            temporary.flush()
            os.fsync(temporary.fileno())
        _verify_materialized(temporary_path, reference)
        os.replace(temporary_path, destination)
        temporary_path = None
        installed = True
        os.chmod(destination, 0o600)
        _fsync_directory(destination.parent)
        return _verify_materialized(destination, reference)
    except RuntimeOptionsError:
        if installed:
            destination.unlink(missing_ok=True)
        raise
    except Exception as exc:
        if installed:
            destination.unlink(missing_ok=True)
        raise RuntimeOptionsError(f"cannot materialize {reference.kind} reference: {exc}") from exc
    finally:
        if callable(stream_close):
            try:
                stream_close()
            except Exception:
                LOGGER.warning("artifact stream close failed")
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def materialize_artifact_reference(
    reference: ArtifactReference,
    manifest: ReleaseManifest,
    root: Path | str,
    environment: str,
    *,
    destination_root: Path | str | None = None,
    object_loader: ObjectLoader | None = None,
    allowed_object_store_origins: set[str] | frozenset[str] | None = None,
    max_artifact_bytes: int | None = None,
) -> Path:
    """Materialize and verify one portable reference at an execution boundary."""

    from .release_manifest import ManifestError, resolve_artifact

    effective_max = _effective_max_artifact_bytes(max_artifact_bytes)
    if reference.kind == "artifact":
        assert reference.artifact_id is not None
        artifact = next(
            (item for item in manifest.artifacts if item.id == reference.artifact_id),
            None,
        )
        if artifact is not None and artifact.size_bytes > effective_max:
            raise RuntimeOptionsError(
                f"runtime artifact declared size {artifact.size_bytes} exceeds configured maximum "
                f"of {effective_max} bytes"
            )
        try:
            return resolve_artifact(manifest, reference.artifact_id, root, environment)
        except ManifestError as exc:
            raise RuntimeOptionsError(str(exc)) from exc
    if reference.kind not in {"inline", "object_store"}:
        raise RuntimeOptionsError(f"unknown artifact reference kind: {reference.kind}")
    if destination_root is None:
        raise RuntimeOptionsError(f"destination root is required for {reference.kind} references")
    destination_base = Path(destination_root)
    destination_base.mkdir(parents=True, exist_ok=True)
    try:
        resolved_base = destination_base.resolve(strict=True)
    except OSError as exc:
        raise RuntimeOptionsError(f"cannot resolve destination root: {destination_base}") from exc
    source_name = reference.name or (PurePosixPath(reference.key or "object").name)
    assert reference.sha256 is not None
    assert reference.size_bytes is not None
    if reference.size_bytes > effective_max:
        raise RuntimeOptionsError(
            f"runtime artifact declared size {reference.size_bytes} exceeds configured maximum "
            f"of {effective_max} bytes"
        )
    if reference.kind == "object_store":
        assert reference.endpoint_url is not None
        normalized_allowed = frozenset(
            normalize_object_store_origin(origin, "object-store allowlist origin")
            for origin in (allowed_object_store_origins or ())
        )
        if not normalized_allowed or reference.endpoint_url not in normalized_allowed:
            raise RuntimeOptionsError(
                f"objectStore.endpointUrl is not present in the configured allowlist: {reference.endpoint_url}"
            )
    destination = resolved_base / f"{reference.sha256}-{source_name}"
    if not destination.resolve(strict=False).is_relative_to(resolved_base):
        raise RuntimeOptionsError("materialized reference destination escapes its root")
    if destination.exists():
        try:
            verified = _verify_materialized(destination, reference)
            os.chmod(verified, 0o600)
            return verified
        except RuntimeOptionsError:
            destination.unlink(missing_ok=True)
    if reference.kind == "inline":
        assert reference.content_base64 is not None
        try:
            decoded = base64.b64decode(reference.content_base64, validate=True)
        except ValueError as exc:
            raise RuntimeOptionsError(f"cannot materialize inline reference: {exc}") from exc
        return _atomic_materialize(
            reference,
            destination,
            iter((decoded,)),
            max_artifact_bytes=effective_max,
        )
    else:
        if object_loader is None:
            raise RuntimeOptionsError("object loader is required for object-store references")
        try:
            chunks = object_loader(reference)
        except RuntimeOptionsError:
            raise
        except Exception as exc:
            raise RuntimeOptionsError(f"object-store reference is unavailable: {exc}") from exc
        return _atomic_materialize(
            reference,
            destination,
            chunks,
            max_artifact_bytes=effective_max,
        )
