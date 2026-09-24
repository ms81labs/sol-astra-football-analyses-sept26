"""6.3 provider execution adapters extracted from llm.py."""

from __future__ import annotations

import base64
import hashlib
import json
from decimal import Decimal, ROUND_UP
from io import BytesIO
from typing import Any, Callable, Literal

from pydantic import Field, model_validator

from .provider_images import MAX_IMAGE_BYTES, MAX_MANIFEST_IMAGES, ProviderImage
from .workbench.contracts import StrictModel
from .workbench.money import money, text

CONFIGURED_DEFAULT = "disabled_until_policy"
LOCAL_MODEL_ID = "deepseek-r1:1.5b"

Validator = Callable[[str, Any], dict]


def _strict_report_schema(value):
    if isinstance(value, list):
        return [_strict_report_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: _strict_report_schema(item) for key, item in value.items()
              if key not in {"title", "default"}}
    if result.get("type") == "object":
        result["additionalProperties"] = False
        result["required"] = list(result.get("properties", {}))
    return result


class EventProposalDraft(StrictModel):
    type: Literal["pass", "turnover", "recovery", "shot", "none"]
    frameId: int = Field(ge=0)
    team: Literal["my_team", "enemy"] | None
    description: str = Field(min_length=1, max_length=512)


class QuerySuccessorDraft(StrictModel):
    kind: str
    team: Literal["same", "opponent", "my_team", "enemy"] | None = None
    period: int | None = Field(default=None, ge=1, le=4)
    withinSeconds: float | None = Field(default=None, gt=0, le=600, allow_inf_nan=False)


class QueryFilterDraft(StrictModel):
    eventFamily: str
    team: Literal["my_team", "enemy"] | None = None
    period: int | None = Field(default=None, ge=1, le=4)
    playerTrackId: int | None = Field(default=None, ge=0, le=1_000_000)
    reviewStatus: Literal["accepted", "unreviewed"] | None = None
    pitchRegion: Literal["left_third", "middle_third", "right_third"] | None = None
    successor: QuerySuccessorDraft | None = None
    timeStartSeconds: float | None = Field(default=None, ge=0, le=86_400, allow_inf_nan=False)
    timeEndSeconds: float | None = Field(default=None, ge=0, le=86_400, allow_inf_nan=False)


class QueryProposalDraft(StrictModel):
    status: Literal["query", "unsupported"]
    reason: Literal["none", "unsupported_vocabulary", "ambiguous_scope", "unsupported_operation"]
    query: QueryFilterDraft | None

    @model_validator(mode="after")
    def valid_disposition(self) -> "QueryProposalDraft":
        if (self.status == "query") != (self.query is not None) \
                or (self.status == "query") != (self.reason == "none"):
            raise ValueError("Query proposal disposition does not match its filter")
        return self


def _astra_format(task_type: str = "tactical_report"):
    from .report_contracts import ReportDraft
    if task_type == "event_proposal":
        name, model = "event_proposal_v1", EventProposalDraft
    elif task_type == "query_proposal":
        name, model = "query_proposal_v1", QueryProposalDraft
    elif task_type in {"tactical_report", "drills"}:
        name, model = "report_draft_v1", ReportDraft
    else:
        raise ValueError("Unsupported Astra task")
    return {"format": {"type": "json_schema", "name": name,
        "strict": True, "schema": _strict_report_schema(model.model_json_schema())}}


def _unique_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Astra JSON output contains a duplicate key")
        result[key] = value
    return result


def build_astra_request(prompt: str, images: list[tuple[ProviderImage, bytes]], *,
                        approved_images: tuple[dict[str, Any], ...], max_output_tokens: int,
                        task_type: str = "tactical_report") -> dict[str, Any]:
    if not isinstance(prompt, str) or not prompt or len(prompt.encode()) > 256 * 1024:
        raise ValueError("invalid bounded Astra prompt")
    if type(max_output_tokens) is not int or not 0 < max_output_tokens <= 25_000:
        raise ValueError("invalid Astra output token ceiling")
    if len(images) > MAX_MANIFEST_IMAGES:
        raise ValueError("too many Astra image parts")
    content = [{"type": "input_text", "text": prompt}]
    identities = set()
    actual_refs = []
    from PIL import Image
    for reference, payload in images:
        if not isinstance(reference, ProviderImage) or not isinstance(payload, bytes) \
                or not 0 < len(payload) <= MAX_IMAGE_BYTES:
            raise ValueError("invalid approved image part")
        ref = ProviderImage.model_validate(reference.model_dump())
        if len(payload) != ref.imageBytes or hashlib.sha256(payload).hexdigest() != ref.imageSha256:
            raise ValueError("approved image bytes do not match reference")
        with Image.open(BytesIO(payload)) as image:
            if image.format != "PNG" or image.size != (ref.width, ref.height):
                raise ValueError("approved image shape does not match reference")
            image.load()
        identities.add((ref.matchId, ref.generationId, ref.sourceSha256))
        actual_refs.append(ref.model_dump(mode="json"))
        content.append({"type": "input_image", "detail": "high",
                        "image_url": "data:image/png;base64," + base64.b64encode(payload).decode()})
    if len(identities) > 1:
        raise ValueError("mixed source image scope")
    if tuple(actual_refs) != approved_images:
        raise ValueError("image parts are not the server-approved evidence")
    return {"model": "gpt-6-astra", "input": [{"role": "user", "content": content}],
        "text": _astra_format(task_type), "max_output_tokens": max_output_tokens,
        "reasoning": {"effort": "low"}, "tools": [], "tool_choice": "none",
        "parallel_tool_calls": False, "service_tier": "default", "store": False,
        "background": False}


def bound_astra_request(body: dict[str, Any], *, input_price_per_million: str,
                        output_price_per_million: str, authorised_limit: str,
                        task_type: str = "tactical_report") -> dict[str, Any]:
    expected = {"model", "input", "text", "max_output_tokens", "reasoning", "tools",
                "tool_choice", "parallel_tool_calls", "service_tier", "store", "background"}
    if not isinstance(body, dict) or set(body) != expected or body.get("model") != "gpt-6-astra" \
            or body.get("text") != _astra_format(task_type) or body.get("reasoning") != {"effort": "low"} \
            or body.get("tools") != [] or body.get("tool_choice") != "none" \
            or body.get("parallel_tool_calls") is not False or body.get("service_tier") != "default" \
            or body.get("store") is not False or body.get("background") is not False:
        raise ValueError("Astra request is not fixed to a tool-free default service mode")
    output_limit = body["max_output_tokens"]
    if type(output_limit) is not int or not 0 < output_limit <= 25_000:
        raise ValueError("invalid Astra output token ceiling")
    messages = body.get("input")
    if not isinstance(messages, list) or len(messages) != 1 or not isinstance(messages[0], dict) \
            or set(messages[0]) != {"role", "content"} or messages[0]["role"] != "user":
        raise ValueError("Astra request must contain one approved message")
    content = messages[0]["content"]
    if not isinstance(content, list) or not 1 <= len(content) <= MAX_MANIFEST_IMAGES + 1 \
            or not isinstance(content[0], dict) or set(content[0]) != {"type", "text"} \
            or content[0]["type"] != "input_text" or not isinstance(content[0]["text"], str):
        raise ValueError("Astra request has invalid text or image parts")
    for part in content[1:]:
        if not isinstance(part, dict) or set(part) != {"type", "detail", "image_url"} \
                or part["type"] != "input_image" or part["detail"] != "high" \
                or not isinstance(part["image_url"], str) \
                or not part["image_url"].startswith("data:image/png;base64,"):
            raise ValueError("Astra request has invalid image part")
        encoded_image = part["image_url"].removeprefix("data:image/png;base64,")
        if len(encoded_image) > 4 * ((MAX_IMAGE_BYTES + 2) // 3):
            raise ValueError("Astra image exceeds byte ceiling")
        payload = base64.b64decode(encoded_image, validate=True)
        if not 0 < len(payload) <= MAX_IMAGE_BYTES:
            raise ValueError("Astra image exceeds byte ceiling")
    priced = json.loads(json.dumps(body))
    for part in priced["input"][0]["content"][1:]:
        part["image_url"] = "data:image/png;base64,"
    text_bytes = len(json.dumps(priced, sort_keys=True, separators=(",", ":")).encode())
    if text_bytes > 256 * 1024:
        raise ValueError("Astra request text exceeds byte ceiling")
    # ponytail: two tokens per UTF-8 byte plus fixed message overhead is a loose
    # ceiling; retain it until real billed usage can justify a tighter policy.
    image_tokens = 3001 * (len(content) - 1)
    input_tokens = 2 * text_bytes + 4096 + image_tokens
    input_price, output_price, limit = (money(item) for item in
        (input_price_per_million, output_price_per_million, authorised_limit))
    if not 0 < input_price and 0 < output_price and 0 < limit:
        raise ValueError("positive verified prices and authorised budget required")
    maximum = ((input_tokens * input_price + output_limit * output_price) / Decimal(1_000_000)).quantize(
        Decimal("0.000000000001"), rounding=ROUND_UP)
    if maximum > limit:
        raise ValueError("Astra request exceeds authorised budget")
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return {"schemaVersion": 1, "modelId": "gpt-6-astra", "requestSha256": hashlib.sha256(encoded).hexdigest(),
        "maxInputTokens": input_tokens, "maxImageTokens": image_tokens,
        "maxOutputTokens": output_limit, "toolsEnabled": False, "serviceTier": "default",
        "maximumCost": text(maximum), "currency": "USD"}


def parse_astra_response(response: dict[str, Any], bound: dict[str, Any]) -> tuple[dict, dict]:
    from .report_contracts import ReportDraft
    if not isinstance(response, dict) or not isinstance(bound, dict) \
            or response.get("model") != bound.get("modelId") \
            or response.get("service_tier") != bound.get("serviceTier") \
            or response.get("status") != "completed" \
            or response.get("incomplete_details") is not None or response.get("error") is not None \
            or not isinstance(response.get("id"), str) or not 0 < len(response["id"]) <= 512:
        raise ValueError("Astra response is not a completed bounded request")
    outputs = response.get("output")
    if not isinstance(outputs, list) or any(not isinstance(item, dict) or
            item.get("type") not in {"reasoning", "message"} for item in outputs):
        raise ValueError("Astra response contains unsupported output")
    messages = [item for item in outputs if item["type"] == "message"]
    if len(messages) != 1 or messages[0].get("role") != "assistant" \
            or messages[0].get("status") != "completed":
        raise ValueError("Astra response must contain one completed assistant message")
    content = messages[0].get("content")
    if not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], dict) \
            or content[0].get("type") != "output_text" or not isinstance(content[0].get("text"), str) \
            or len(content[0]["text"].encode()) > 1_000_000:
        raise ValueError("Astra response must contain one bounded JSON output")
    usage = response.get("usage")
    if not isinstance(usage, dict) or any(type(usage.get(key)) is not int for key in
            ("input_tokens", "output_tokens", "total_tokens")) \
            or not 0 <= usage["input_tokens"] <= bound.get("maxInputTokens", -1) \
            or not 0 <= usage["output_tokens"] <= bound.get("maxOutputTokens", -1) \
            or usage["total_tokens"] != usage["input_tokens"] + usage["output_tokens"]:
        raise ValueError("Astra response usage is missing or exceeds its bound")
    model = (EventProposalDraft if bound.get("taskType") == "event_proposal" else
             QueryProposalDraft if bound.get("taskType") == "query_proposal" else ReportDraft)
    draft = model.model_validate(json.loads(content[0]["text"], object_pairs_hook=_unique_json_keys))
    return draft.model_dump(mode="json"), {"responseId": response["id"],
        "inputTokens": usage["input_tokens"], "outputTokens": usage["output_tokens"]}


def execute_astra_bound(request: dict, bound: dict, *, transport: Callable[[dict, float], bytes],
                        timeout_seconds: float) -> tuple[dict, dict]:
    from .provider_billing import ProviderNotDispatched
    if not isinstance(request, dict) or not isinstance(bound, dict) \
            or bound.get("modelId") != "gpt-6-astra" or bound.get("serviceTier") != "default" \
            or bound.get("toolsEnabled") is not False \
            or bound.get("requestSha256") != hashlib.sha256(json.dumps(request,
                sort_keys=True, separators=(",", ":")).encode()).hexdigest() \
            or type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= 120:
        raise ProviderNotDispatched("Astra request changed before dispatch")
    raw = transport(request, timeout_seconds)
    if not isinstance(raw, bytes) or len(raw) > 1_000_000:
        raise ValueError("Astra response exceeds byte limit")
    response = json.loads(raw, object_pairs_hook=_unique_json_keys)
    return parse_astra_response(response, bound)


def astra_http_transport(request: dict, timeout_seconds: float, *, api_key: str) -> bytes:
    import requests
    import time
    from .provider_billing import ProviderNotDispatched
    if not isinstance(api_key, str) or not 0 < len(api_key) <= 512 \
            or not api_key.isascii() or any(char.isspace() or not char.isprintable() for char in api_key) \
            or type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= 120:
        raise ProviderNotDispatched("Astra credentials or deadline unavailable before dispatch")
    encoded = json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
    chunks = []
    size = 0
    started = time.monotonic()
    with requests.post("https://api.openai.com/v1/responses", data=encoded,
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
            stream=True, timeout=timeout_seconds, allow_redirects=False) as response:
        if response.status_code != 200:
            raise ValueError("Astra HTTP status is not successful")
        for chunk in response.iter_content(chunk_size=65_536):
            if time.monotonic() - started > timeout_seconds:
                raise TimeoutError("Astra response deadline exceeded")
            if not isinstance(chunk, bytes):
                raise ValueError("Astra response contains non-byte content")
            size += len(chunk)
            if size > 1_000_000:
                raise ValueError("Astra response exceeds byte limit")
            chunks.append(chunk)
    if time.monotonic() - started > timeout_seconds:
        raise TimeoutError("Astra response deadline exceeded")
    return b"".join(chunks)


def make_astra_adapter(api_key: str, *, transport=astra_http_transport, local_adapter=None):
    """Use the gateway's reserved request; leave provider billing unsettled."""
    from .provider_billing import ProviderNotDispatched, ProviderResult
    from .provider_gateway import is_valid_gateway_token

    def adapter(analysis_type, frames, *, gateway_token=None, provider=None, model_id=None,
                deadline_seconds=120, prepared_request=None, execution_bound=None, **kwargs):
        if not is_valid_gateway_token(gateway_token):
            raise ProviderNotDispatched("Astra gateway reservation is required")
        if provider == "local":
            from .llm import run_analysis
            return (local_adapter or run_analysis)(analysis_type, frames, gateway_token=gateway_token,
                provider=provider, model_id=model_id, deadline_seconds=deadline_seconds, **kwargs)
        if provider != "cloud" or model_id != "gpt-6-astra" or not isinstance(execution_bound, dict) \
                or execution_bound.get("adapterId") != "astra-responses-v1" \
                or execution_bound.get("taskType") != analysis_type:
            raise ProviderNotDispatched("Astra gateway reservation is required")
        draft, _tokens = execute_astra_bound(prepared_request, execution_bound,
            transport=lambda request, seconds: transport(request, seconds, api_key=api_key),
            timeout_seconds=deadline_seconds)
        return ProviderResult(draft)  # Token counts do not prove the final invoice.

    adapter.billing_contract_id = "astra-responses-v1"
    return adapter


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
