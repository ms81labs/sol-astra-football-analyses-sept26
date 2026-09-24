"""W07: mocked transport proves a source-bound proposal reaches review without a paid call."""

import json

import pytest

from backend.app.provider_adapters import make_astra_adapter
from backend.app.provider_billing import AstraSpendPolicy, ProviderBudgetLedger
from backend.app.provider_gateway import ProviderGateway
from backend.app.provider_images import select_source_image_manifest
from backend.app.settings import ProcessingSettings
from backend.app.storage import Storage
from backend.tests.test_audit_v3_final_journey import _install_video


@pytest.mark.integration
@pytest.mark.real_media
def test_mocked_event_request_produces_reviewable_source_bound_receipt(tmp_path):
    storage = Storage(tmp_path / "store")
    match_id = _install_video(storage, tmp_path)
    config = storage.get_match(match_id).config.model_copy(deep=True)
    config.rights.cloudPermission = True
    config.rights.processingScope = "local_plus_burst"
    storage.update_match_config(match_id, config)
    generation_id = storage.current_generation(match_id).generationId
    manifest = select_source_image_manifest(storage, match_id, generation_id, [0])
    sent = []
    revoke_during_transport = [False]

    def transport(request, timeout, *, api_key):
        sent.append(request)
        if revoke_during_transport[0]:
            revoked = storage.get_match(match_id).config.model_copy(deep=True)
            revoked.rights.cloudPermission = False
            storage.update_match_config(match_id, revoked)
        return json.dumps({"id": "mock-event-1", "model": "gpt-6-astra", "status": "completed",
            "service_tier": "default", "incomplete_details": None, "error": None,
            "output": [{"type": "message", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": json.dumps({
                    "type": "shot", "frameId": 0, "team": None, "description": "Possible shot"})}]}],
            "usage": {"input_tokens": 100, "output_tokens": 100, "total_tokens": 200}}).encode()

    spend = AstraSpendPolicy(task_types=("event_proposal",), max_output_tokens=4096,
        input_price_per_million="22", output_price_per_million="82.5")
    settings = ProcessingSettings(cloud_provider_enabled=True, cloud_provider_api_key="test-only",
        allowed_model_ids=("gpt-6-astra",), cloud_model_id="gpt-6-astra",
        provider_call_reservation=5, provider_budget_limit=10, provider_spend_policy=spend)
    gateway = ProviderGateway(storage, settings,
        adapter_factory=lambda: make_astra_adapter("test-only", transport=transport),
        budget_ledger=ProviderBudgetLedger(storage.job_ledger.db_path, 10))
    receipt = gateway.execute_event_proposal(match_id, body={"generationId": generation_id,
        "imageManifestDigest": manifest, "requestId": "visual-review-1"})
    assert len(sent) == 1
    assert sent[0]["text"]["format"]["name"] == "event_proposal_v1"
    assert receipt["schemaVersion"] == "event_proposal_receipt_v1"
    assert receipt["sourceSha256"] == storage.source_sha256(match_id)
    assert receipt["proposal"]["evidenceIds"] == ["frame:0"]
    assert receipt["proposal"]["modelId"] == "gpt-6-astra"
    assert storage.job_ledger.provider_result(receipt["requestId"]) == receipt
    assert storage.job_ledger.latest_attempt(receipt["requestId"]).status == "complete"
    assert gateway.execute_event_proposal(match_id, body={"generationId": generation_id,
        "imageManifestDigest": manifest, "requestId": "visual-review-1"}) == receipt
    assert len(sent) == 1
    from backend.app.report_store import StaleReportPolicy
    revoke_during_transport[0] = True
    with pytest.raises(StaleReportPolicy):
        gateway.execute_event_proposal(match_id, body={"generationId": generation_id,
            "imageManifestDigest": manifest, "requestId": "visual-review-stale"})
    assert len(sent) == 2
    requests = [request for request in storage.job_ledger.requests.values()
        if request.matchId == match_id and request.providerTask == "event_proposal"]
    stale_id = next(request.requestId for request in requests if request.requestId != receipt["requestId"])
    assert storage.job_ledger.provider_result(stale_id) is None
    assert storage.job_ledger.latest_attempt(stale_id).status == "complete"
    storage.submit_correction(match_id, kind="event_propose",
        payload={**receipt["proposal"], "providerRequestId": receipt["requestId"]})
    assert any(event.proposalRequestId == receipt["requestId"] for event in storage.load_events(match_id))
    assert storage.job_ledger.cost_for(receipt["requestId"])["billingComplete"] is False


@pytest.mark.integration
@pytest.mark.real_media
def test_event_proposal_api_refuses_cloud_disabled_without_dispatch(tmp_path):
    from fastapi.testclient import TestClient
    from backend.app.main import create_app

    root = tmp_path / "store"
    storage = Storage(root)
    match_id = _install_video(storage, tmp_path)
    generation_id = storage.current_generation(match_id).generationId
    manifest = select_source_image_manifest(storage, match_id, generation_id, [0])
    client = TestClient(create_app(storage_root=root), base_url="http://127.0.0.1")
    response = client.post(f"/api/matches/{match_id}/event-proposals", json={
        "generationId": generation_id, "imageManifestDigest": manifest,
        "requestId": "disabled-cloud"})
    assert response.status_code == 403, response.text
    assert Storage(root).job_ledger.cost_summary()["attemptCount"] == 0
