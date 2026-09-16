"""6.3 language-provider adapters, split from llm.py and disabled by default."""

from __future__ import annotations


def provider_roster() -> dict[str, object]:
    return {
        "default": "disabled",
        "adapters": {
            "local": "template_fallback",
            "cloud": "gated",
        },
    }


def local_adapter(*, enabled: bool = False) -> dict[str, str]:
    if not enabled:
        return {"route": "disabled"}
    return {"route": "template"}


def cloud_adapter(*, enabled: bool = False) -> dict[str, str]:
    if not enabled:
        return {"route": "disabled"}
    raise RuntimeError("cloud provider is not authorised")
