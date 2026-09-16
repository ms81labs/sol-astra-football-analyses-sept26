from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Final


class DaytonaPolicyError(ValueError):
    """Raised when the committed Daytona execution policy is not exact and safe."""


_RELEASE_DIR: Final = Path(__file__).parent
_POLICY_PATH: Final = _RELEASE_DIR / "daytona-v7.3.json"
_MAX_POLICY_BYTES: Final = 16_384
_EXPECTED_IMAGE: Final = (
    "docker.io/pytorch/pytorch@sha256:"
    "417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385"
)
_EXPECTED_KEYS: Final = frozenset(
    {
        "schemaVersion",
        "sdkVersion",
        "image",
        "target",
        "cpu",
        "memoryGiB",
        "diskGiB",
        "gpu",
        "gpuTypes",
        "spot",
        "public",
        "ephemeral",
        "networkBlockAll",
        "ttlMinutes",
        "createTimeoutSeconds",
        "executionTimeoutSeconds",
        "transferTimeoutSeconds",
        "deleteTimeoutSeconds",
        "cleanupAttempts",
    }
)


def _canonical_json_bytes(value: object) -> bytes:
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise DaytonaPolicyError("Daytona policy is not canonical JSON") from exc
    return (encoded + "\n").encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DaytonaPolicyError("Daytona policy contains a duplicate key")
        result[key] = value
    return result


def _decode_policy(raw: bytes) -> dict[str, object]:
    if type(raw) is not bytes or not raw or len(raw) > _MAX_POLICY_BYTES:
        raise DaytonaPolicyError("Daytona policy bytes are invalid")
    unexpected_value_error = False
    try:
        text = raw.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                DaytonaPolicyError("Daytona policy contains a non-finite number")
            ),
        )
    except DaytonaPolicyError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DaytonaPolicyError("Daytona policy is not valid JSON") from exc
    except ValueError:
        unexpected_value_error = True
    if unexpected_value_error:
        raise DaytonaPolicyError("Daytona policy is not valid JSON")
    if type(value) is not dict:
        raise DaytonaPolicyError("Daytona policy must be a plain JSON object")
    if raw != _canonical_json_bytes(value):
        raise DaytonaPolicyError("Daytona policy bytes are not canonical")
    return value


def _require_exact(mapping: dict[str, object], key: str, expected: object) -> object:
    value = mapping[key]
    if type(value) is not type(expected) or value != expected:
        raise DaytonaPolicyError(f"Daytona policy field {key} is invalid")
    return value


@dataclass(frozen=True, slots=True)
class DaytonaPolicy:
    schema_version: int
    sdk_version: str
    image: str
    target: str
    cpu: int
    memory_gib: int
    disk_gib: int
    gpu: int
    gpu_types: tuple[str, str]
    spot: bool
    public: bool
    ephemeral: bool
    network_block_all: bool
    ttl_minutes: int
    create_timeout_seconds: int
    execution_timeout_seconds: int
    transfer_timeout_seconds: int
    delete_timeout_seconds: int
    cleanup_attempts: int

    def __post_init__(self) -> None:
        expected_fields = (
            ("schemaVersion", self.schema_version, 1),
            ("sdkVersion", self.sdk_version, "0.207.0"),
            ("image", self.image, _EXPECTED_IMAGE),
            ("target", self.target, "us"),
            ("cpu", self.cpu, 4),
            ("memoryGiB", self.memory_gib, 8),
            ("diskGiB", self.disk_gib, 10),
            ("gpu", self.gpu, 1),
            ("gpuTypes", self.gpu_types, ("RTX-PRO-6000", "H100")),
            ("spot", self.spot, False),
            ("public", self.public, False),
            ("ephemeral", self.ephemeral, True),
            ("networkBlockAll", self.network_block_all, True),
            ("ttlMinutes", self.ttl_minutes, 180),
            ("createTimeoutSeconds", self.create_timeout_seconds, 600),
            ("executionTimeoutSeconds", self.execution_timeout_seconds, 9000),
            ("transferTimeoutSeconds", self.transfer_timeout_seconds, 1800),
            ("deleteTimeoutSeconds", self.delete_timeout_seconds, 120),
            ("cleanupAttempts", self.cleanup_attempts, 3),
        )
        for json_name, value, expected in expected_fields:
            if type(value) is not type(expected) or value != expected:
                raise DaytonaPolicyError(f"Daytona policy field {json_name} is invalid")

    @classmethod
    def from_mapping(cls, mapping: object) -> "DaytonaPolicy":
        if type(mapping) is not dict:
            raise DaytonaPolicyError("Daytona policy must be a plain JSON object")
        if set(mapping) != _EXPECTED_KEYS:
            raise DaytonaPolicyError("Daytona policy keys do not match the exact contract")

        gpu_types = mapping["gpuTypes"]
        if type(gpu_types) is not list or any(type(item) is not str for item in gpu_types):
            raise DaytonaPolicyError("Daytona policy field gpuTypes is invalid")

        _require_exact(mapping, "schemaVersion", 1)
        _require_exact(mapping, "sdkVersion", "0.207.0")
        _require_exact(mapping, "image", _EXPECTED_IMAGE)
        _require_exact(mapping, "target", "us")
        _require_exact(mapping, "cpu", 4)
        _require_exact(mapping, "memoryGiB", 8)
        _require_exact(mapping, "diskGiB", 10)
        _require_exact(mapping, "gpu", 1)
        _require_exact(mapping, "gpuTypes", ["RTX-PRO-6000", "H100"])
        _require_exact(mapping, "spot", False)
        _require_exact(mapping, "public", False)
        _require_exact(mapping, "ephemeral", True)
        _require_exact(mapping, "networkBlockAll", True)
        _require_exact(mapping, "ttlMinutes", 180)
        _require_exact(mapping, "createTimeoutSeconds", 600)
        _require_exact(mapping, "executionTimeoutSeconds", 9000)
        _require_exact(mapping, "transferTimeoutSeconds", 1800)
        _require_exact(mapping, "deleteTimeoutSeconds", 120)
        _require_exact(mapping, "cleanupAttempts", 3)

        return cls(
            schema_version=1,
            sdk_version="0.207.0",
            image=_EXPECTED_IMAGE,
            target="us",
            cpu=4,
            memory_gib=8,
            disk_gib=10,
            gpu=1,
            gpu_types=("RTX-PRO-6000", "H100"),
            spot=False,
            public=False,
            ephemeral=True,
            network_block_all=True,
            ttl_minutes=180,
            create_timeout_seconds=600,
            execution_timeout_seconds=9000,
            transfer_timeout_seconds=1800,
            delete_timeout_seconds=120,
            cleanup_attempts=3,
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "schemaVersion": self.schema_version,
            "sdkVersion": self.sdk_version,
            "image": self.image,
            "target": self.target,
            "cpu": self.cpu,
            "memoryGiB": self.memory_gib,
            "diskGiB": self.disk_gib,
            "gpu": self.gpu,
            "gpuTypes": list(self.gpu_types),
            "spot": self.spot,
            "public": self.public,
            "ephemeral": self.ephemeral,
            "networkBlockAll": self.network_block_all,
            "ttlMinutes": self.ttl_minutes,
            "createTimeoutSeconds": self.create_timeout_seconds,
            "executionTimeoutSeconds": self.execution_timeout_seconds,
            "transferTimeoutSeconds": self.transfer_timeout_seconds,
            "deleteTimeoutSeconds": self.delete_timeout_seconds,
            "cleanupAttempts": self.cleanup_attempts,
        }


def _read_committed_policy() -> bytes:
    path = _POLICY_PATH
    release_dir = _RELEASE_DIR
    if (
        not isinstance(path, Path)
        or not isinstance(release_dir, Path)
        or not path.is_absolute()
        or path.parent != release_dir
        or path.name != "daytona-v7.3.json"
    ):
        raise DaytonaPolicyError("Daytona committed policy path is invalid")
    try:
        before = path.lstat()
    except OSError as exc:
        raise DaytonaPolicyError("Daytona committed policy path is unavailable") from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise DaytonaPolicyError("Daytona committed policy path is not a regular file")
    if before.st_size <= 0 or before.st_size > _MAX_POLICY_BYTES:
        raise DaytonaPolicyError("Daytona committed policy file size is invalid")

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISREG(opened.st_mode)
                or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
                or opened.st_size != before.st_size
            ):
                raise DaytonaPolicyError("Daytona committed policy file changed during open")
            raw = b""
            while len(raw) <= _MAX_POLICY_BYTES:
                chunk = os.read(descriptor, min(4096, _MAX_POLICY_BYTES + 1 - len(raw)))
                if not chunk:
                    break
                raw += chunk
        finally:
            os.close(descriptor)
    except DaytonaPolicyError:
        raise
    except OSError as exc:
        raise DaytonaPolicyError("Daytona committed policy path could not be read safely") from exc
    if len(raw) != before.st_size:
        raise DaytonaPolicyError("Daytona committed policy file changed during read")
    return raw


def load_daytona_policy() -> DaytonaPolicy:
    mapping = _decode_policy(_read_committed_policy())
    return DaytonaPolicy.from_mapping(mapping)
