"""C03: stored compatibility reports cannot bypass payload validation.

These tests deliberately recompute the storage checksum after malformed writes:
checksums detect changed bytes, but do not replace schema/scope validation.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.report_contracts import digest
from backend.app.report_store import ReportStore
from backend.tests.test_audit_v3_c03_reports import _gateway, _interprets, _store

pytestmark = pytest.mark.integration


def _legacy(*args, **kwargs):
    package = kwargs["approved_evidence"]
    return {"summary": "REFERENCED_LEGACY_SENTINEL", "evidence": [next(iter(package["aliases"]))]}


def _record(storage, mid, result):
    path = (storage.generations.root(mid) / "reports" / result["generationId"]
            / "tactical_report" / f"{result['reportId']}.json")
    return path, json.loads(path.read_text())


def _rewrite(path, record):
    record.pop("contentDigest")
    record["contentDigest"] = digest(record)
    path.write_text(json.dumps(record))
    return path.read_bytes()


@pytest.mark.parametrize("mode", ["legacy", "scoped"])
@pytest.mark.parametrize("fault", ["cross_match", "cross_generation", "unscoped_reference", "false_grounding"])
def test_all_stored_report_schemas_enforce_scope_and_disposition(tmp_path, mode, fault):
    storage, mid = _store(tmp_path)
    result = _gateway(storage, _legacy if mode == "legacy" else _interprets).execute(mid, "tactical_report")
    path, record = _record(storage, mid, result)
    payload = record["payload"]
    if fault == "false_grounding":
        payload["grounding"] = "grounded"
        payload["validationDisposition"] = "grounded"
        record["validationDisposition"] = "grounded"
    else:
        # Supply a well-formed reference to isolate scope from JSON shape.
        payload["evidence"] = [{"matchId": mid, "generationId": result["generationId"],
                                "kind": "frame", "localId": "0"}]
        if fault == "cross_match":
            payload["evidence"][0]["matchId"] = "foreign-match"
        elif fault == "cross_generation":
            payload["evidence"][0]["generationId"] = "foreign-generation"
        else:
            payload["evidence"] = ["invented-unscoped-reference"]
    before = _rewrite(path, record)
    view = ReportStore(storage).view(mid)
    assert not view["reports"]
    assert any(item["code"] == "REPORT_VERIFICATION_REQUIRED" for item in view["notices"])
    assert path.read_bytes() == before


@pytest.mark.parametrize("fault", ["number_summary", "empty_references", "bad_recommendations", "bad_measurements"])
def test_malformed_legacy_payload_is_isolated_before_html_rendering(tmp_path, fault):
    storage, mid = _store(tmp_path)
    result = _gateway(storage, _legacy).execute(mid, "tactical_report")
    path, record = _record(storage, mid, result)
    payload = record["payload"]
    if fault == "number_summary":
        payload["summary"] = 42
    elif fault == "empty_references":
        payload["evidence"] = []
    elif fault == "bad_recommendations":
        payload["recommendations"] = [None]
    else:
        payload["measurements"] = [{"metric": "possession_pct", "value": True}]
    before = _rewrite(path, record)
    with TestClient(create_app(storage_root=storage.storage_root), base_url="http://127.0.0.1") as client:
        response = client.get(f"/api/matches/{mid}/report/html")
    assert response.status_code == 200, response.text
    assert "REPORT_VERIFICATION_REQUIRED" in response.text
    assert "REFERENCED_LEGACY_SENTINEL" not in response.text
    assert path.read_bytes() == before


@pytest.mark.parametrize("mode", ["legacy", "scoped"])
def test_valid_compatibility_and_interpretive_payloads_remain_readable(tmp_path, mode):
    storage, mid = _store(tmp_path)
    result = _gateway(storage, _legacy if mode == "legacy" else _interprets).execute(mid, "tactical_report")
    path, record = _record(storage, mid, result)
    before = path.read_bytes()
    selected = ReportStore(storage).view(mid)["reports"]["tactical_report"]
    assert selected["payload"] == record["payload"]
    assert selected["validationDisposition"] == ("referenced" if mode == "legacy" else "interpretive")
    assert path.read_bytes() == before


@pytest.mark.parametrize("mode", ["legacy", "scoped"])
@pytest.mark.parametrize("with_advice", [False, True])
def test_valid_stored_metrics_keep_grounded_claims_without_grounding_advice(tmp_path, mode, with_advice):
    from backend.tests.test_audit_v3_c03_reports import _claim, _draft

    storage, mid = _store(tmp_path)

    def adapter(*args, **kwargs):
        package = kwargs["approved_evidence"]
        metric = next(item for item in package["metrics"] if item["value"] is not None)
        if mode == "legacy":
            payload = {"measurements": [_claim(metric)]}
        else:
            payload = _draft(package, metricClaims=[_claim(metric)])
        if with_advice:
            payload["interpretation"] = "Consider reviewing spacing; this is advice, not a measured fact."
        return payload

    result = _gateway(storage, adapter).execute(mid, "tactical_report")
    record = ReportStore(storage).view(mid)["reports"]["tactical_report"]
    assert record["validationDisposition"] == ("interpretive" if with_advice else "grounded")
    field = "measurements" if mode == "legacy" else "metricClaims"
    assert record["payload"][field][0]["grounding"] == "grounded"
    assert result["reportId"] == record["reportId"]
