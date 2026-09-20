"""6.3 provider execution adapters extracted from llm.py."""

from __future__ import annotations

import json
from typing import Any, Callable

CONFIGURED_DEFAULT = "disabled_until_policy"
LOCAL_MODEL_ID = "deepseek-r1:1.5b"

Validator = Callable[[str, Any], dict]


def execute_local(prompt: str, analysis_type: str, validate: Validator, *, timeout_seconds: float = 120.0) -> dict:
    import requests

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": LOCAL_MODEL_ID, "prompt": prompt, "stream": False, "format": "json"},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return validate(analysis_type, json.loads(response.json()["response"]))


def execute_cloud(
    prompt: str,
    analysis_type: str,
    validate: Validator,
    *,
    timeout_seconds: float = 120.0,
    model_id: str | None = None,
) -> dict:
    # The old fixed reservation cannot bound reasoning/tool/provider usage.
    # Keep real cloud execution disabled until its complete billing contract is qualified.
    raise ValueError("CLOUD_SPEND_BOUND_UNQUALIFIED")
