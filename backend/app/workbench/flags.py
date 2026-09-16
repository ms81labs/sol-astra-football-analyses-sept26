"""Feature flags for shadowed metrics, GPU promotion and native code (GA-09/17/18)."""

from __future__ import annotations

import os

DEFAULT_FLAGS = {
    "experimental_shot_quality": False,
    "gpu_default": False,
    "native_code": False,
}


def feature_enabled(name: str, env: dict[str, str] | None = None) -> bool:
    source = env if env is not None else os.environ
    env_key = "GA_FLAG_" + name.upper()
    raw = str(source.get(env_key, "")).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return bool(DEFAULT_FLAGS.get(name, False))


def feature_flags(env: dict[str, str] | None = None) -> dict[str, bool]:
    return {name: feature_enabled(name, env=env) for name in DEFAULT_FLAGS}
