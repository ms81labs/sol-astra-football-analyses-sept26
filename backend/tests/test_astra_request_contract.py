"""W06: offline Astra request and spend envelope; no provider transport."""

import base64
import hashlib
from io import BytesIO

import pytest
from PIL import Image

from backend.app.provider_adapters import build_astra_request, bound_astra_request
from backend.app.provider_images import ProviderImage


def _image():
    output = BytesIO()
    Image.new("RGB", (2, 2), "red").save(output, format="PNG")
    payload = output.getvalue()
    reference = ProviderImage(matchId="m", generationId="g", sourceSha256="a" * 64,
        sourceFrameId=2, ptsSeconds=0.5, sourceWidth=2, sourceHeight=2,
        crop=(0, 0, 2, 2), width=2, height=2,
        imageSha256=hashlib.sha256(payload).hexdigest(), imageBytes=len(payload))
    return reference, payload


def test_astra_request_is_strict_single_call_with_real_image_parts_and_no_tools():
    reference, payload = _image()
    approved = (reference.model_dump(mode="json"),)
    body = build_astra_request("Approved frame evidence", [(reference, payload)],
        approved_images=approved, max_output_tokens=4096)
    assert body["model"] == "gpt-6-astra"
    assert body["service_tier"] == "default"
    assert body["tools"] == [] and body["tool_choice"] == "none"
    assert body["store"] is False and body["background"] is False
    assert body["reasoning"] == {"effort": "low"}
    content = body["input"][0]["content"]
    assert content[0] == {"type": "input_text", "text": "Approved frame evidence"}
    assert content[1] == {"type": "input_image", "detail": "high",
        "image_url": "data:image/png;base64," + base64.b64encode(payload).decode()}
    schema = body["text"]["format"]
    assert schema["type"] == "json_schema" and schema["strict"] is True
    assert set(schema["schema"]["required"]) == set(schema["schema"]["properties"])
    assert schema["schema"]["additionalProperties"] is False
    bound = bound_astra_request(body, input_price_per_million="11", output_price_per_million="41.25",
        authorised_limit="1")
    assert bound["maxImageTokens"] == 3001
    assert bound["maxOutputTokens"] == 4096
    assert bound["toolsEnabled"] is False and bound["serviceTier"] == "default"
    assert float(bound["maximumCost"]) <= 1


def test_astra_request_rejects_changed_pixels_and_unbounded_or_billed_modes():
    reference, payload = _image()
    with pytest.raises(ValueError, match="image"):
        build_astra_request("x", [(reference, payload + b"x")],
            approved_images=(reference.model_dump(mode="json"),), max_output_tokens=4096)
    with pytest.raises(ValueError, match="approved"):
        build_astra_request("x", [(reference, payload)], approved_images=(), max_output_tokens=4096)
    with pytest.raises(ValueError, match="output"):
        build_astra_request("x", [], approved_images=(), max_output_tokens=0)
    body = build_astra_request("x", [(reference, payload)],
        approved_images=(reference.model_dump(mode="json"),), max_output_tokens=4096)
    body["tools"] = [{"type": "web_search"}]
    with pytest.raises(ValueError, match="fixed"):
        bound_astra_request(body, input_price_per_million="11", output_price_per_million="41.25",
            authorised_limit="1")
    body["tools"] = []
    with pytest.raises(ValueError, match="budget"):
        bound_astra_request(body, input_price_per_million="11", output_price_per_million="41.25",
            authorised_limit="0.001")


def test_astra_request_without_visuals_contains_only_text():
    body = build_astra_request("No source image is available", [],
        approved_images=(), max_output_tokens=1024)
    assert body["input"][0]["content"] == [
        {"type": "input_text", "text": "No source image is available"}]
    bound = bound_astra_request(body, input_price_per_million="11",
        output_price_per_million="41.25", authorised_limit="1")
    assert bound["maxImageTokens"] == 0


def test_event_proposal_uses_distinct_strict_schema_and_rejects_report_shape():
    from backend.app.provider_adapters import parse_astra_response

    reference, payload = _image()
    request = build_astra_request("Review source frame 2", [(reference, payload)],
        approved_images=(reference.model_dump(mode="json"),), max_output_tokens=4096,
        task_type="event_proposal")
    assert request["text"]["format"]["name"] == "event_proposal_v1"
    assert set(request["text"]["format"]["schema"]["required"]) == {"type", "frameId", "team", "description"}
    bound = bound_astra_request(request, input_price_per_million="22",
        output_price_per_million="82.5", authorised_limit="5", task_type="event_proposal")
    with pytest.raises(ValueError, match="fixed"):
        bound_astra_request(request, input_price_per_million="22",
            output_price_per_million="82.5", authorised_limit="5")
    response = {"id": "resp_event", "model": "gpt-6-astra", "status": "completed",
        "service_tier": "default", "incomplete_details": None, "error": None,
        "output": [{"type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": '{"type":"shot","frameId":2,"team":null,"description":"Possible shot"}'}]}],
        "usage": {"input_tokens": 100, "output_tokens": 100, "total_tokens": 200}}
    parsed, _ = parse_astra_response(response, {**bound, "taskType": "event_proposal"})
    assert parsed == {"type": "shot", "frameId": 2, "team": None, "description": "Possible shot"}
    with pytest.raises(ValueError):
        parse_astra_response({**response, "output": [{"type": "message", "role": "assistant",
            "status": "completed", "content": [{"type": "output_text",
            "text": '{"type":"shot","frameId":2,"team":null,"description":"Possible shot","modelId":"client"}'}]}]},
            {**bound, "taskType": "event_proposal"})


def test_query_proposal_has_strict_text_only_schema_and_rejects_code_fields():
    import json
    from backend.app.provider_adapters import parse_astra_response

    request = build_astra_request("Find recoveries", [], approved_images=(),
        max_output_tokens=4096, task_type="query_proposal")
    assert request["text"]["format"]["name"] == "query_proposal_v1"
    assert request["input"][0]["content"] == [{"type": "input_text", "text": "Find recoveries"}]
    bound = bound_astra_request(request, input_price_per_million="22",
        output_price_per_million="82.5", authorised_limit="5", task_type="query_proposal")
    draft = {"status": "query", "reason": "none", "query": {"eventFamily": "recovery",
        "team": None, "period": None, "playerTrackId": None, "reviewStatus": None,
        "pitchRegion": None, "successor": None, "timeStartSeconds": None, "timeEndSeconds": None}}
    response = {"id": "resp_query", "model": "gpt-6-astra", "status": "completed",
        "service_tier": "default", "incomplete_details": None, "error": None,
        "output": [{"type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": json.dumps(draft)}]}],
        "usage": {"input_tokens": 100, "output_tokens": 100, "total_tokens": 200}}
    parsed, _ = parse_astra_response(response, {**bound, "taskType": "query_proposal"})
    assert parsed == draft
    with pytest.raises(ValueError):
        parse_astra_response({**response, "output": [{"type": "message", "role": "assistant",
            "status": "completed", "content": [{"type": "output_text",
            "text": json.dumps({**draft, "query": {**draft["query"], "sql": "SELECT *"}})}]}]},
            {**bound, "taskType": "query_proposal"})


def test_astra_response_requires_one_completed_draft_with_bounded_usage():
    from backend.app.provider_adapters import parse_astra_response
    from backend.app.report_contracts import ReportDraft
    draft = ReportDraft(schemaVersion="report_draft_v1", matchId="m", generationId="g",
        taskType="tactical_report")
    response = {"id": "resp_1", "model": "gpt-6-astra", "status": "completed",
        "service_tier": "default", "incomplete_details": None, "error": None,
        "output": [{"type": "reasoning"}, {"type": "message", "role": "assistant",
            "status": "completed", "content": [{"type": "output_text",
                "text": draft.model_dump_json()}]}],
        "usage": {"input_tokens": 200, "output_tokens": 100, "total_tokens": 300}}
    bound = {"modelId": "gpt-6-astra", "serviceTier": "default",
        "maxInputTokens": 500, "maxOutputTokens": 200}
    parsed, usage = parse_astra_response(response, bound)
    assert parsed == draft.model_dump(mode="json")
    assert usage == {"responseId": "resp_1", "inputTokens": 200, "outputTokens": 100}
    for changed in (
        {"status": "incomplete"}, {"service_tier": "priority"},
        {"output": response["output"] + [{"type": "function_call"}]},
        {"output": [{"type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "refusal", "refusal": "no"}]}]},
        {"usage": {"input_tokens": 501, "output_tokens": 100, "total_tokens": 601}},
        {"usage": None},
        {"output": [{"type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": draft.model_dump_json()[:-1]
                + ',"matchId":"wrong"}'}]}]},
    ):
        with pytest.raises(ValueError):
            parse_astra_response({**response, **changed}, bound)


def test_astra_transport_checks_reserved_body_before_submission_and_caps_reply():
    import json
    from backend.app.provider_adapters import execute_astra_bound
    from backend.app.provider_billing import ProviderNotDispatched
    from backend.app.report_contracts import ReportDraft

    request = build_astra_request("Approved evidence", [], approved_images=(), max_output_tokens=1024)
    bound = bound_astra_request(request, input_price_per_million="20",
        output_price_per_million="75", authorised_limit="1")
    draft = ReportDraft(schemaVersion="report_draft_v1", matchId="m", generationId="g",
        taskType="tactical_report")
    response = {"id": "mock-1", "model": "gpt-6-astra", "service_tier": "default",
        "status": "completed", "incomplete_details": None, "error": None,
        "output": [{"type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": draft.model_dump_json()}]}],
        "usage": {"input_tokens": 50, "output_tokens": 50, "total_tokens": 100}}
    calls = []
    def transport(body, timeout):
        calls.append((body, timeout))
        return json.dumps(response).encode()
    parsed, usage = execute_astra_bound(request, bound, transport=transport, timeout_seconds=5)
    assert parsed == draft.model_dump(mode="json")
    assert usage["responseId"] == "mock-1" and calls == [(request, 5)]
    with pytest.raises(ProviderNotDispatched):
        execute_astra_bound({**request, "store": True}, bound,
            transport=transport, timeout_seconds=5)
    assert len(calls) == 1
    with pytest.raises(ValueError, match="byte limit"):
        execute_astra_bound(request, bound, transport=lambda *_: b"x" * 1_000_001,
            timeout_seconds=5)


def test_astra_http_transport_sends_canonical_json_and_caps_stream(monkeypatch):
    import json
    from backend.app.provider_adapters import astra_http_transport
    from backend.app.provider_billing import ProviderNotDispatched
    import requests

    request = build_astra_request("Approved evidence", [], approved_images=(), max_output_tokens=1024)
    calls = []
    class Response:
        def __init__(self, chunks): self.chunks = chunks
        status_code = 200
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def raise_for_status(self): pass
        def iter_content(self, chunk_size):
            assert chunk_size == 65_536
            yield from self.chunks
    chunks = [b'{"status":"completed"}']
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response(chunks)
    monkeypatch.setattr(requests, "post", post)
    assert astra_http_transport(request, 5, api_key="test-key") == chunks[0]
    url, kwargs = calls[0]
    assert url == "https://api.openai.com/v1/responses"
    assert kwargs["data"] == json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert kwargs["stream"] is True and kwargs["timeout"] == 5
    assert kwargs["allow_redirects"] is False
    chunks[:] = [b"x" * 1_000_000, b"y"]
    with pytest.raises(ValueError, match="byte limit"):
        astra_http_transport(request, 5, api_key="test-key")
    with pytest.raises(ProviderNotDispatched):
        astra_http_transport(request, 5, api_key="")
    assert len(calls) == 2
    class Redirect(Response):
        status_code = 302
    monkeypatch.setattr(requests, "post", lambda *_, **__: Redirect([b"redirect"]))
    with pytest.raises(ValueError, match="HTTP status"):
        astra_http_transport(request, 5, api_key="test-key")
    import time
    chunks[:] = [b"one", b"two"]
    monotonic = iter((0, 6))
    monkeypatch.setattr(time, "monotonic", lambda: next(monotonic))
    monkeypatch.setattr(requests, "post", post)
    with pytest.raises(TimeoutError):
        astra_http_transport(request, 5, api_key="test-key")
    chunks[:] = []
    monotonic = iter((0, 6))
    with pytest.raises(TimeoutError):
        astra_http_transport(request, 5, api_key="test-key")


def test_guarded_astra_adapter_uses_bound_request_and_leaves_billing_unsettled():
    import json
    from backend.app.provider_adapters import make_astra_adapter
    from backend.app.provider_billing import AstraSpendPolicy, ProviderResult
    from backend.app.provider_gateway import ProviderGateway
    from backend.app.report_contracts import ReportDraft
    from backend.app.settings import ProcessingSettings

    request = build_astra_request("Approved evidence", [], approved_images=(), max_output_tokens=4096)
    policy = AstraSpendPolicy(task_types=("tactical_report",), max_output_tokens=4096,
        input_price_per_million="22", output_price_per_million="82.5")
    bound = policy.bind_request(request, task="tactical_report", model="gpt-6-astra", authorised_limit="5")
    draft = ReportDraft(schemaVersion="report_draft_v1", matchId="m", generationId="g",
        taskType="tactical_report")
    response = {"id": "mock-response", "model": "gpt-6-astra", "status": "completed",
        "service_tier": "default", "incomplete_details": None, "error": None,
        "output": [{"type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": draft.model_dump_json()}]}],
        "usage": {"input_tokens": 100, "output_tokens": 100, "total_tokens": 200}}
    calls = []
    def transport(body, timeout, *, api_key):
        calls.append((body, timeout, api_key))
        return json.dumps(response).encode()
    adapter = make_astra_adapter("test-only", transport=transport)
    token = ProviderGateway(None, ProcessingSettings(), adapter_factory=lambda: adapter)._token
    result = adapter("tactical_report", [], gateway_token=token, provider="cloud",
        model_id="gpt-6-astra", deadline_seconds=5, prepared_request=request,
        execution_bound=bound)
    assert isinstance(result, ProviderResult)
    assert result.output["taskType"] == "tactical_report"
    assert result.usage is None  # API token counts are not a settled provider invoice.
    assert calls == [(request, 5, "test-only")]
    local_calls = []
    fallback = make_astra_adapter("test-only", transport=transport,
        local_adapter=lambda *args, **kwargs: local_calls.append((args, kwargs)) or {"offline": True})
    assert fallback("tactical_report", [], gateway_token=token, provider="local") == {"offline": True}
    assert len(local_calls) == 1 and len(calls) == 1
    with pytest.raises(ValueError):
        adapter("tactical_report", [], gateway_token=token, provider="cloud",
            model_id="gpt-6-astra", deadline_seconds=5,
            prepared_request={**request, "store": True}, execution_bound=bound)
    assert len(calls) == 1


def test_app_selects_astra_adapter_only_for_explicit_spend_policy(tmp_path):
    from backend.app.main import create_app
    from backend.app.provider_billing import AstraSpendPolicy
    from backend.app.settings import ProcessingSettings

    default = create_app(storage_root=tmp_path / "default")
    assert getattr(default.state.provider_gateway.adapter_factory(), "billing_contract_id", None) is None
    policy = AstraSpendPolicy(task_types=("tactical_report",), max_output_tokens=4096,
        input_price_per_million="22", output_price_per_million="82.5")
    settings = ProcessingSettings(cloud_provider_enabled=True, cloud_provider_api_key="test-only",
        allowed_model_ids=("gpt-6-astra",), cloud_model_id="gpt-6-astra",
        provider_call_reservation=5, provider_budget_limit=10, provider_spend_policy=policy)
    app = create_app(storage_root=tmp_path / "astra", settings=settings)
    assert app.state.provider_gateway.adapter_factory().billing_contract_id == "astra-responses-v1"
