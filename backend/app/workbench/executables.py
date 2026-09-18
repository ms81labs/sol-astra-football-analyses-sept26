"""Resolve media executables through one fail-closed trust boundary."""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path
from typing import Literal, Protocol

from .hashing import stream_sha256


_DEFAULT_TRUSTED_BIN_DIRS = (
    Path("/usr/bin"),
    Path("/usr/local/bin"),
    Path("/opt/homebrew/bin"),
)


class ExecutableSettings(Protocol):
    trusted_bin_dirs: tuple[str, ...]
    ffmpeg_sha256: str | None
    ffprobe_sha256: str | None


def resolve_trusted_executable(
    name: Literal["ffmpeg", "ffprobe"],
    *,
    configured: str | None = None,
    settings: ExecutableSettings | None = None,
) -> Path:
    candidate = configured or shutil.which(name)
    if candidate is None:
        raise FileNotFoundError(name)
    raw = Path(candidate)
    if configured is not None and not raw.is_absolute():
        raise ValueError("configured media executable must be absolute")
    resolved = raw.resolve(strict=True)
    metadata = resolved.stat()
    if (
        resolved.name not in {name, f"{name}.exe"}
        or not stat.S_ISREG(metadata.st_mode)
        or not os.access(resolved, os.X_OK)
        or metadata.st_mode & stat.S_IWOTH
    ):
        raise ValueError("media executable is not trusted")
    environment_dirs = tuple(
        Path(item).resolve()
        for item in os.environ.get("GA_TRUSTED_BIN_DIRS", "").split(os.pathsep)
        if item
    )
    settings_dirs = tuple(
        Path(item).resolve() for item in getattr(settings, "trusted_bin_dirs", ())
    )
    trusted_dirs = tuple(directory.resolve() for directory in _DEFAULT_TRUSTED_BIN_DIRS) + environment_dirs + settings_dirs
    expected_sha = getattr(settings, f"{name}_sha256", None) or os.environ.get(f"GA_{name.upper()}_SHA256")
    trusted_location = resolved.parent in trusted_dirs
    trusted_digest = bool(expected_sha) and stream_sha256(resolved).sha256 == expected_sha
    if not trusted_location and not trusted_digest:
        raise ValueError("media executable is outside trusted directories")
    return resolved
