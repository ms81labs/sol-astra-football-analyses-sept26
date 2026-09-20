"""6.3 provider execution adapters extracted from llm.py."""

from __future__ import annotations

import json
import os
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
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured.")
    model = model_id or os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-haiku")
    import httpx

    with httpx.Client(timeout=timeout_seconds) as client:
        resp = client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://guerilla-analytics.local",
                "X-Title": "Guerilla Analytics",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        try:
            return validate(analysis_type, json.loads(content))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"OpenRouter returned non-JSON: {content[:200]}") from exc
