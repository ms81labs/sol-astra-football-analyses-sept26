"""Physical output-path confinement for the research sidecar."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


_DEFAULT_RUN_ROOT_NAME = "fotball-analyst-research-addon"
_PROTECTED_PRODUCT_NAMES = ("backend", "frontend", "detector", "analytics", "truth-gate")


class PathResolutionError(Exception):
    """Raised when an output path is outside the sidecar boundary."""


def get_addon_root() -> Path:
    """Return the physical addon root derived from this installed package."""
    package_root = Path(__file__).resolve().parent
    project_root = package_root.parent
    if (
        project_root.name == "research-addon"
        and (project_root / "research_addon").resolve() == package_root
    ):
        return project_root
    return package_root


def get_default_run_root() -> Path:
    """Return the dedicated temporary execution root."""
    return Path(tempfile.gettempdir()).expanduser().resolve() / _DEFAULT_RUN_ROOT_NAME


def get_default_manifest_path() -> Path:
    """Return the manifest path directly beneath the addon root."""
    return get_addon_root() / "corpus-manifest.json"


def _contains(root: Path, candidate: Path) -> bool:
    return candidate == root or root in candidate.parents


def _reject(path: Path) -> PathResolutionError:
    return PathResolutionError(
        f"Rejected output path: {path}\n"
        "Path must be inside the addon root, the dedicated temporary root, "
        "or an existing owned temporary directory"
    )


def _validate_owned_directory(path: Path) -> None:
    if path.is_symlink() or not path.is_dir() or path.stat().st_uid != os.geteuid():
        raise _reject(path)


def _resolve_output_directory(path: str | Path | None) -> Path:
    addon_root = get_addon_root()
    checkout_root = addon_root.parent
    temp_root = Path(tempfile.gettempdir()).expanduser().resolve()
    default_root = temp_root / _DEFAULT_RUN_ROOT_NAME
    requested = default_root if path is None else Path(path).expanduser()
    if ".." in requested.parts:
        raise _reject(requested)
    lexical = Path(os.path.abspath(requested))

    if requested.is_symlink():
        raise _reject(requested)

    resolved = requested.resolve()
    blocked = tuple(checkout_root / name for name in _PROTECTED_PRODUCT_NAMES) + (
        checkout_root / ".factory",
    )
    if any(
        _contains(root, lexical) or _contains(root.resolve(), resolved)
        for root in blocked
    ):
        raise _reject(resolved)

    try:
        checkout_relative = resolved.relative_to(checkout_root)
    except ValueError:
        checkout_relative = None
    if (
        checkout_relative
        and checkout_relative.parts
        and checkout_relative.parts[0] != addon_root.name
        and checkout_relative.parts[0].startswith(addon_root.name)
    ):
        raise _reject(resolved)

    if _contains(addon_root, lexical) and not _contains(addon_root, resolved):
        raise _reject(resolved)
    if _contains(addon_root, resolved):
        if resolved.exists() and not resolved.is_dir():
            raise _reject(resolved)
        return resolved

    if default_root.exists() or default_root.is_symlink():
        _validate_owned_directory(default_root)
    default_physical = default_root.resolve()
    if _contains(default_root, lexical) and not _contains(default_physical, resolved):
        raise _reject(resolved)
    if _contains(default_physical, resolved):
        if resolved.exists():
            _validate_owned_directory(resolved)
        return resolved

    if resolved == temp_root or not _contains(temp_root, resolved):
        raise _reject(resolved)
    if not requested.exists():
        raise _reject(resolved)
    _validate_owned_directory(requested)
    return resolved


def resolve_run_root(storage_root: str | Path | None = None) -> Path:
    """Resolve an allowed addon or temporary execution directory."""
    return _resolve_output_directory(storage_root)


def resolve_manifest_path(path: str | Path | None = None) -> Path:
    """Resolve a manifest output without allowing a symlink target."""
    requested = get_default_manifest_path() if path is None else Path(path).expanduser()
    if requested.is_symlink():
        raise _reject(requested)
    parent = _resolve_output_directory(requested.parent)
    resolved = requested.resolve()
    if resolved.parent != parent:
        raise _reject(resolved)
    return resolved
