from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from ipaddress import IPv6Address
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from backend.release.daytona_policy import (
    DaytonaPolicy,
    DaytonaPolicyError,
    load_daytona_policy,
)


ProcessingBackend = Literal["local", "daytona"]
DeploymentMode = Literal["local", "hosted"]
DEFAULT_MAX_UPLOAD_BYTES = 8 * 1024**3
DEFAULT_TRUSTED_FRONTEND_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://[::1]:5173",
)
DEFAULT_TRUSTED_BIN_DIRS = ("/usr/bin", "/usr/local/bin", "/opt/homebrew/bin")


class SettingsError(ValueError):
    """Raised when processing configuration is invalid or incomplete."""


def canonicalize_origin(value: str) -> str:
    """Validate an HTTP(S) origin, preserving scheme/host/effective-port identity."""
    try:
        if not isinstance(value, str) or any(ord(char) <= 32 or ord(char) >= 127 for char in value):
            raise ValueError
        if any(char in value for char in "@\\?#*%"):
            raise ValueError
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
        if parsed.scheme not in {"http", "https"} or not host or parsed.path or parsed.netloc.endswith(":"):
            raise ValueError
        if ":" in host:
            host = f"[{IPv6Address(host).compressed}]"
        elif not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in host.removesuffix(".").split(".")):
            raise ValueError
        default_port = 80 if parsed.scheme == "http" else 443
        suffix = f":{port}" if port is not None and port != default_port else ""
        return f"{parsed.scheme}://{host}{suffix}"
    except ValueError:
        raise SettingsError("trusted_frontend_origins must contain only valid HTTP(S) origins") from None


@dataclass(frozen=True, slots=True)
class ProcessingSettings:
    processing_backend: ProcessingBackend = "local"
    daytona_api_key: str | None = field(default=None, repr=False)
    daytona_policy: DaytonaPolicy | None = None
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
    trusted_frontend_origins: tuple[str, ...] = DEFAULT_TRUSTED_FRONTEND_ORIGINS
    cloud_provider_enabled: bool = False
    cloud_provider_api_key: str | None = field(default=None, repr=False)
    allowed_model_ids: tuple[str, ...] = ()
    cloud_model_id: str = "anthropic/claude-3.5-haiku"
    provider_deadline_seconds: float = 30.0
    provider_call_reservation: float = 0.0
    trusted_bin_dirs: tuple[str, ...] = DEFAULT_TRUSTED_BIN_DIRS
    ffmpeg_sha256: str | None = None
    ffprobe_sha256: str | None = None
    deployment_mode: DeploymentMode = "local"
    auth_backend: Literal["hmac"] | None = None
    auth_secret: str | None = field(default=None, repr=False)
    bind_host: str = "127.0.0.1"
    tls_terminated: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.trusted_frontend_origins, tuple) or not self.trusted_frontend_origins:
            raise SettingsError("trusted_frontend_origins must be a nonempty tuple of HTTP(S) origins")
        origins = tuple(dict.fromkeys(
            canonicalize_origin(origin.strip() if isinstance(origin, str) else origin)
            for origin in self.trusted_frontend_origins
        ))
        object.__setattr__(self, "trusted_frontend_origins", origins)
        if type(self.max_upload_bytes) is not int or self.max_upload_bytes <= 0:
            raise SettingsError("max_upload_bytes must be a positive integer")
        if type(self.processing_backend) is not str or self.processing_backend not in {
            "local",
            "daytona",
        }:
            raise SettingsError("processing_backend must be exactly 'local' or 'daytona'")
        if self.provider_deadline_seconds <= 0 or self.provider_call_reservation < 0:
            raise SettingsError("provider deadline must be positive and reservation nonnegative")
        if not all(Path(directory).is_absolute() for directory in self.trusted_bin_dirs):
            raise SettingsError("trusted_bin_dirs must contain absolute paths")
        if self.deployment_mode not in {"local", "hosted"}:
            raise SettingsError("deployment_mode must be exactly 'local' or 'hosted'")
        if self.processing_backend == "local":
            if self.daytona_api_key is not None or self.daytona_policy is not None:
                raise SettingsError("local processing cannot include Daytona configuration")
            return
        if type(self.daytona_api_key) is not str or not self.daytona_api_key.strip():
            raise SettingsError("daytona_api_key is required for Daytona processing")
        if type(self.daytona_policy) is not DaytonaPolicy:
            raise SettingsError("daytona_policy is required for Daytona processing")

    @property
    def remote_enabled(self) -> bool:
        return self.processing_backend == "daytona"

    def to_safe_mapping(self) -> dict[str, object]:
        return {
            "processingBackend": self.processing_backend,
            "remoteEnabled": self.remote_enabled,
        }

    def validate_deployment(self) -> None:
        if self.deployment_mode != "hosted":
            return
        if self.auth_backend != "hmac" or not self.auth_secret:
            raise SettingsError("hosted deployment requires an authentication backend and secret")
        if os.environ.get("GA_FLAG_LEFTOVER_HTTP") == "1":
            raise SettingsError("hosted deployment requires leftover HTTP routes to be disabled")
        if self.bind_host not in {"127.0.0.1", "localhost", "::1"} and not self.tls_terminated:
            raise SettingsError("hosted deployment on a non-loopback bind requires TLS termination")

    @classmethod
    def from_env(cls) -> "ProcessingSettings":
        raw_origins = os.environ.get("TRUSTED_FRONTEND_ORIGINS")
        trusted_frontend_origins = (
            DEFAULT_TRUSTED_FRONTEND_ORIGINS if raw_origins is None else tuple(raw_origins.split(","))
        )
        trusted_bin_dirs = DEFAULT_TRUSTED_BIN_DIRS + tuple(
            item for item in os.environ.get("GA_TRUSTED_BIN_DIRS", "").split(os.pathsep) if item
        )
        raw_max_upload_bytes = os.environ.get("MATCH_UPLOAD_MAX_BYTES")
        try:
            max_upload_bytes = (
                DEFAULT_MAX_UPLOAD_BYTES
                if raw_max_upload_bytes is None
                else int(raw_max_upload_bytes)
            )
        except ValueError:
            raise SettingsError("MATCH_UPLOAD_MAX_BYTES must be a positive integer") from None
        if max_upload_bytes <= 0:
            raise SettingsError("MATCH_UPLOAD_MAX_BYTES must be a positive integer")

        backend = os.environ.get("PROCESSING_BACKEND", "local")
        if backend not in {"local", "daytona"}:
            raise SettingsError("PROCESSING_BACKEND must be exactly 'local' or 'daytona'")
        if backend == "local":
            return cls(
                max_upload_bytes=max_upload_bytes,
                trusted_frontend_origins=trusted_frontend_origins,
                cloud_provider_enabled=os.environ.get("GA_CLOUD_PROVIDER_ENABLED") == "1",
                cloud_provider_api_key=os.environ.get("OPENROUTER_API_KEY"),
                allowed_model_ids=tuple(filter(None, os.environ.get("GA_ALLOWED_MODEL_IDS", "").split(","))),
                cloud_model_id=os.environ.get("OPENROUTER_MODEL", "anthropic/claude-3.5-haiku"),
                trusted_bin_dirs=trusted_bin_dirs,
                ffmpeg_sha256=os.environ.get("GA_FFMPEG_SHA256"),
                ffprobe_sha256=os.environ.get("GA_FFPROBE_SHA256"),
                deployment_mode=os.environ.get("GA_DEPLOYMENT_MODE", "local"),
                auth_backend=os.environ.get("GA_AUTH_BACKEND"),
                auth_secret=os.environ.get("GA_AUTH_SECRET"),
                bind_host=os.environ.get("GA_BIND_HOST", "127.0.0.1"),
                tls_terminated=os.environ.get("GA_TLS_TERMINATED") == "1",
            )

        api_key = os.environ.get("DAYTONA_API_KEY")
        if api_key is None or not api_key.strip():
            raise SettingsError("DAYTONA_API_KEY is required for Daytona processing")
        try:
            policy = load_daytona_policy()
        except DaytonaPolicyError as exc:
            raise SettingsError("Daytona policy is invalid") from exc
        return cls(
            processing_backend="daytona",
            daytona_api_key=api_key,
            daytona_policy=policy,
            max_upload_bytes=max_upload_bytes,
            trusted_frontend_origins=trusted_frontend_origins,
            trusted_bin_dirs=trusted_bin_dirs,
            ffmpeg_sha256=os.environ.get("GA_FFMPEG_SHA256"),
            ffprobe_sha256=os.environ.get("GA_FFPROBE_SHA256"),
            deployment_mode=os.environ.get("GA_DEPLOYMENT_MODE", "local"),
            auth_backend=os.environ.get("GA_AUTH_BACKEND"),
            auth_secret=os.environ.get("GA_AUTH_SECRET"),
            bind_host=os.environ.get("GA_BIND_HOST", "127.0.0.1"),
            tls_terminated=os.environ.get("GA_TLS_TERMINATED") == "1",
        )
