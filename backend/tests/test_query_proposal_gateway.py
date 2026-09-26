"""W07 model query proposals stay inside the existing typed Python executor."""

import json

import pytest

from backend.app.provider_adapters import make_astra_adapter
from backend.app.provider_billing import AstraSpendPolicy, ProviderBudgetLedger
from backend.app.provider_gateway import ProviderGateway
from backend.app.settings import ProcessingSettings
from backend.tests.test_audit_v3_c03_reports import _store


@pytest.mark.integration
def test_mocked_query_proposal_is_scoped_validated_and_executed_by_typed_search(tmp_path):
    from backend.app.workbench.assistance import validate_query_proposal

    storage, match_id = _store(tmp_path)
    config = storage.get_match(match_id).config.model_copy(deep=True)
    config.rights.cloudPermission = True
    config.rights.processingScope = "local_plus_burst"
    storage.update_match_config(match_id, config)
    generation_id = storage.current_generation(match_id).generationId
    calls = []
    draft = {"status": "query", "reason": "none", "query": {"eventFamily": "recovery",
        "team": None, "period": None, "playerTrackId": None, "reviewStatus": None,
        "pitchRegion": None, "successor": None, "timeStartSeconds": None, "timeEndSeconds": None}}

    def transport(request, timeout, *, api_key):
        calls.append(request)
        return json.dumps({"id": "mock-query-1", "model": "gpt-6-astra", "status": "completed",
            "service_tier": "default", "incomplete_details": None, "error": None,
            "output": [{"type": "message", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": json.dumps(draft)}]}],
            "usage": {"input_tokens": 100, "output_tokens": 100, "total_tokens": 200}}).encode()

    spend = AstraSpendPolicy(task_types=("query_proposal",), max_output_tokens=4096,
        input_price_per_million="22", output_price_per_million="82.5")
    settings = ProcessingSettings(cloud_provider_enabled=True, cloud_provider_api_key="test-only",
        allowed_model_ids=("gpt-6-astra",), cloud_model_id="gpt-6-astra",
        provider_call_reservation=5, provider_budget_limit=10, provider_spend_policy=spend)
    gateway = ProviderGateway(storage, settings,
        adapter_factory=lambda: make_astra_adapter("test-only", transport=transport),
        budget_ledger=ProviderBudgetLedger(storage.job_ledger.db_path, 10))
    body = {"generationId": generation_id, "question": "Find recoveries", "requestId": "find-recoveries"}
    receipt = gateway.execute_query_proposal(match_id, body=body)
    expected = storage.query_match_events(match_id, validate_query_proposal({
        "matchId": match_id, "generationId": generation_id,
        "query": {key: value for key, value in draft["query"].items() if value is not None}},
        match_id=match_id, generation_id=generation_id))
    assert receipt["schemaVersion"] == "query_proposal_receipt_v1"
    assert receipt["sourceSha256"] == storage.source_sha256(match_id)
    assert receipt["query"] == expected["query"]
    assert receipt["results"] == expected["results"]
    assert receipt["coverageState"] == expected["coverageState"]
    assert calls[0]["text"]["format"]["name"] == "query_proposal_v1"
    assert gateway.execute_query_proposal(match_id, body=body) == receipt
    assert len(calls) == 1
    assert storage.job_ledger.provider_result(receipt["requestId"]) == receipt
    assert storage.job_ledger.latest_attempt(receipt["requestId"]).status == "complete"

    draft.update(status="unsupported", reason="unsupported_operation", query=None)
    refused = gateway.execute_query_proposal(match_id, body={**body, "requestId": "unsupported"})
    assert refused["query"] == {"unanswerable": True, "reason": "unsupported_operation"}
    assert refused["results"] == []
    assert refused["coverageState"] == "unsupported"

    # A schema-valid but unsupported filter is billed; it must be recorded and
    # replayable rather than leaving the request key permanently unusable.
    draft.update(status="query", reason="none", query={"eventFamily": "dribble", **{key: None for key in (
        "team", "period", "playerTrackId", "reviewStatus", "pitchRegion", "successor",
        "timeStartSeconds", "timeEndSeconds")}})
    calls_before = len(calls)
    invalid_body = {**body, "requestId": "invalid-family"}
    rejected = gateway.execute_query_proposal(match_id, body=invalid_body)
    assert rejected["query"] == {"unanswerable": True, "reason": "invalid_model_output"}
    assert rejected["results"] == [] and rejected["coverageState"] == "unsupported"
    assert gateway.execute_query_proposal(match_id, body=invalid_body) == rejected
    assert len(calls) == calls_before + 1

    draft.update(status="query", reason="none", query={
        "eventFamily": "recovery", "sql": "SELECT * FROM events"})
    with pytest.raises(ValueError):
        gateway.execute_query_proposal(match_id, body={**body, "requestId": "invented-sql"})


@pytest.mark.integration
def test_query_proposal_api_refuses_cloud_disabled_without_reservation(tmp_path):
    from fastapi.testclient import TestClient
    from backend.app.main import create_app

    storage, match_id = _store(tmp_path)
    generation_id = storage.current_generation(match_id).generationId
    attempts_before = storage.job_ledger.cost_summary()["attemptCount"]
    client = TestClient(create_app(storage_root=storage.storage_root), base_url="http://127.0.0.1")
    assert client.get(f"/api/matches/{match_id}/query-proposals").json() == {
        "generationId": generation_id, "available": False}
    response = client.post(f"/api/matches/{match_id}/query-proposals", json={
        "generationId": generation_id, "question": "Find recoveries", "requestId": "disabled-query"})
    assert response.status_code == 403, response.text
    assert storage.job_ledger.cost_summary()["attemptCount"] == attempts_before
