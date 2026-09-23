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
