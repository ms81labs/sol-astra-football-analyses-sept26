"""Persisted report validation and view contracts, with no provider execution."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from backend.app.report_contracts import digest
from backend.app.report_store import ReportStore, validate_record


def _ref(match_id="match", generation_id="generation"):
    return {"matchId": match_id, "generationId": generation_id, "kind": "frame", "localId": "0"}


def _metric(ref):
    return {"metric": "possession", "definitionVersion": "v1", "teamScope": "my_team",
            "intervalStart": 0.0, "intervalEnd": 10.0, "unit": "percent", "value": 50.0,
            "evidence": [deepcopy(ref)], "grounding": "grounded", "availability": "available",
            "publishedLabel": "Observed possession"}


def _document(mode="mixed", match_id="match", generation_id="generation", report_id="report_a"):
    ref = _ref(match_id, generation_id)
    payload = {"schemaVersion": "report_draft_v1", "matchId": match_id,
               "generationId": generation_id, "taskType": "tactical_report",
               "inputEvidenceDigest": "e" * 64, "requiresAnalyst": True,
               "metricClaims": [], "observations": [], "evidence": [deepcopy(ref)]}
    disposition = "grounded"
    if mode in {"metric", "mixed"}:
        payload["metricClaims"] = [_metric(ref)]
    if mode in {"observation", "mixed"}:
        payload["observations"] = [{"text": "A referenced observation", "grounding": "referenced", "evidence": [deepcopy(ref)]}]
        disposition = "referenced"
    if mode in {"advice", "recommendation", "drill"}:
        disposition = "interpretive"
        if mode == "advice":
            payload["interpretation"] = "Review the spacing."
        elif mode == "recommendation":
            payload["recommendations"] = ["Review spacing."]
        else:
            payload["drills"] = [{"name": "Rondo", "objective": "Spacing", "setup": "Circle", "duration": "5 min"}]
    if mode.startswith("legacy"):
        payload.pop("taskType")
        payload.pop("metricClaims")
        payload.pop("observations")
        payload["schemaVersion"] = "legacy_referenced_report_v0"
        if mode == "legacy_summary":
            payload["summary"] = "A referenced legacy observation"
            disposition = "referenced"
        else:
            payload["measurements"] = [_metric(ref)]
    if mode.startswith("deterministic"):
        payload = {"schemaVersion": "deterministic_report_v1", "matchId": match_id,
                   "generationId": generation_id, "inputEvidenceDigest": "e" * 64,
                   "summary": "Stored measurements only", "metrics": [], "events": []}
        disposition = "validation_failed" if mode.endswith("failed") else "deterministic"
    payload["grounding"] = "deterministic" if mode.startswith("deterministic") else disposition
    payload["validationDisposition"] = disposition
    return {"schemaVersion": "report_record_v1", "reportId": report_id, "matchId": match_id,
            "generationId": generation_id, "taskType": "tactical_report", "modelId": "local",
            "provider": "local", "promptVersion": "v1", "outputSchema": payload["schemaVersion"],
            "createdAt": "2026-09-01T12:00:00+00:00", "metadata": {}, "inputEvidenceDigest": "e" * 64,
            "policyRevision": "a" * 64, "validationDisposition": disposition, "payload": payload}


@pytest.mark.parametrize("mode", ["metric", "observation", "mixed", "advice", "recommendation", "drill",
                                  "legacy_summary", "legacy_metric", "deterministic", "deterministic_failed"])
def test_valid_reports_keep_all_supported_schemas_and_do_not_mutate_payloads(mode):
    document = _document(mode)
    before = deepcopy(document)
    assert validate_record(document, "match", "generation", "tactical_report") is None
    assert document == before


@pytest.mark.parametrize("collection", ["evidence", "metricClaims", "observations"])
@pytest.mark.parametrize("fault", ["alias", "foreign_match", "foreign_generation"])
def test_every_reference_collection_rejects_unresolved_or_out_of_scope_references(collection, fault):
    document = _document()
    target = document["payload"]
    refs = target["evidence"] if collection == "evidence" else target[collection][0]["evidence"]
    if fault == "alias":
        refs[0] = "request_alias"
    else:
        refs[0]["matchId" if fault == "foreign_match" else "generationId"] = "foreign"
    before = deepcopy(document)
    with pytest.raises(ValueError, match="Stored evidence reference scope mismatch"):
        validate_record(document, "match", "generation", "tactical_report")
    assert document == before


@pytest.mark.parametrize("field,value,message", [
    ("schemaVersion", "unknown", "Unsupported report record"),
    ("matchId", "foreign", "Report scope mismatch"),
    ("generationId", "foreign", "Report scope mismatch"),
    ("taskType", "drills", "Report scope mismatch"),
    ("reportId", "", "Missing report identity: reportId"),
    ("modelId", 4, "Missing report identity: modelId"),
    ("provider", None, "Missing report identity: provider"),
    ("promptVersion", [], "Missing report identity: promptVersion"),
    ("outputSchema", "", "Missing report identity: outputSchema"),
    ("inputEvidenceDigest", "E" * 64, "Invalid report digest: inputEvidenceDigest"),
    ("policyRevision", "a" * 63, "Invalid report digest: policyRevision"),
    ("createdAt", "2026-09-01T12:00:00", "Report timestamp must be timezone-aware"),
    ("metadata", [], "Invalid report metadata"),
    ("payload", [], "Report payload scope mismatch"),
    ("validationDisposition", "grounded", "Invalid report disposition"),
    ("outputSchema", "other", "Stored output schema mismatch"),
])
def test_envelope_validation_errors_remain_specific(field, value, message):
    document = _document()
    document[field] = value
    with pytest.raises(ValueError, match=message):
        validate_record(document, "match", "generation", "tactical_report")


@pytest.mark.parametrize("collection", ["metricClaims", "observations"])
@pytest.mark.parametrize("items", [{}, [None], "not-a-list"])
def test_malformed_claim_collections_are_rejected_before_model_parsing(collection, items):
    document = _document()
    document["payload"][collection] = items
    with pytest.raises(ValueError, match="Malformed stored report collection"):
        validate_record(document, "match", "generation", "tactical_report")


@pytest.mark.parametrize("collection", ["metricClaims", "observations"])
@pytest.mark.parametrize("fault,message", [("extra", "Unknown stored claim fields"),
                                          ("grounding", "Stored claim disposition mismatch")])
def test_claim_field_and_disposition_checks_precede_metadata_stripping(collection, fault, message):
    document = _document()
    claim = document["payload"][collection][0]
    claim["unexpected" if fault == "extra" else "grounding"] = "invalid"
    with pytest.raises(ValueError, match=message):
        validate_record(document, "match", "generation", "tactical_report")


@pytest.mark.parametrize("availability", [None, "unknown", "unavailable"])
def test_unpublishable_metric_claims_are_not_exposed(availability):
    document = _document("metric")
    document["payload"]["metricClaims"][0]["availability"] = availability
    with pytest.raises(ValueError, match="Stored metric claim is not publishable"):
        validate_record(document, "match", "generation", "tactical_report")


def test_stored_metric_coverage_labels_are_accepted_when_well_formed():
    document = _document("metric")
    document["payload"]["metricClaims"][0].update(
        eligibleSeconds=8.0, requestedSeconds=10, denominator="tracked seconds", reasonCodes=["PARTIAL_COVERAGE"])
    validate_record(document, "match", "generation", "tactical_report")


@pytest.mark.parametrize("fields,message", [
    ({"eligibleSeconds": 11.0, "requestedSeconds": 10.0}, "Malformed stored metric coverage"),
    ({"eligibleSeconds": -1.0, "requestedSeconds": 10.0}, "Malformed stored metric coverage"),
    ({"eligibleSeconds": 5.0}, "Malformed stored metric coverage"),
    ({"eligibleSeconds": True, "requestedSeconds": 10.0}, "Malformed stored metric coverage"),
    ({"eligibleSeconds": float("nan"), "requestedSeconds": 10.0}, "Malformed stored metric coverage"),
    ({"denominator": 3}, "Malformed stored metric denominator"),
    ({"reasonCodes": "PARTIAL"}, "Malformed stored metric limitations"),
    ({"reasonCodes": [1]}, "Malformed stored metric limitations"),
])
def test_malformed_stored_metric_coverage_labels_are_rejected(fields, message):
    document = _document("metric")
    document["payload"]["metricClaims"][0].update(fields)
    with pytest.raises(ValueError, match=message):
        validate_record(document, "match", "generation", "tactical_report")


@pytest.mark.parametrize("field,value,message", [
    ("summary", None, "Malformed deterministic summary"),
    ("metrics", {}, "Malformed deterministic report"),
    ("events", [None], "Malformed deterministic report"),
    ("grounding", "referenced", "Invalid deterministic report"),
])
def test_deterministic_report_shape_keeps_its_existing_error_boundary(field, value, message):
    document = _document("deterministic")
    document["payload"][field] = value
    with pytest.raises(ValueError, match=message):
        validate_record(document, "match", "generation", "tactical_report")


@pytest.mark.parametrize("mode", ["mixed", "legacy_summary"])
def test_unknown_narrative_fields_are_not_silently_removed(mode):
    document = _document(mode)
    document["payload"]["unknown"] = "value"
    with pytest.raises(ValueError, match="Unknown (stored|compatibility) report fields"):
        validate_record(document, "match", "generation", "tactical_report")


def test_multiple_envelope_faults_keep_original_validation_precedence():
    document = _document()
    document.update(reportId="", inputEvidenceDigest="bad", createdAt="bad", metadata=[], payload=[])
    with pytest.raises(ValueError, match="Missing report identity: reportId"):
        validate_record(document, "match", "generation", "tactical_report")
    document["reportId"] = "report_a"
    with pytest.raises(ValueError, match="Invalid report digest: inputEvidenceDigest"):
        validate_record(document, "match", "generation", "tactical_report")


def _write_record(storage, match_id, generation_id, name="report_a", mode="mixed"):
    directory = storage.generations.root(match_id) / "reports" / generation_id / "tactical_report"
    directory.mkdir(parents=True, exist_ok=True)
    document = _document(mode, match_id, generation_id, name)
    document["contentDigest"] = digest(document)
    path = directory / f"{name}.json"
    path.write_text(json.dumps(document))
    return path, document


@pytest.mark.integration
def test_report_view_retains_notice_shapes_order_and_does_not_rewrite_files(tmp_path):
    from backend.tests.test_audit_v3_c03_reports import _store
    storage, mid = _store(tmp_path)
    generation = storage.current_generation(mid).generationId
    path, _ = _write_record(storage, mid, generation)
    path.write_text('{"invalid":true}')
    root = storage.generations.root(mid)
    (root / "tactical_report.json").write_text('{}')
    (root / "drills.json").write_text('{}')
    (root / "reports" / "other_generation").mkdir()
    before = {str(p): p.read_bytes() for p in root.rglob("*.json")}
    view = ReportStore(storage).view(mid)
    assert view["reports"] == {}
    assert view["notices"] == [
        {"taskType": "drills", "code": "REPORT_UNAVAILABLE_FOR_GENERATION"},
        {"taskType": "tactical_report", "code": "REPORT_VERIFICATION_REQUIRED"},
        {"taskType": "tactical_report", "code": "REPORT_UNAVAILABLE_FOR_GENERATION"},
        {"code": "LEGACY_REPORTS_UNVERIFIED", "tasks": ["drills", "tactical_report"]},
        {"code": "OTHER_GENERATION_REPORTS_OMITTED"},
    ]
    assert {str(p): p.read_bytes() for p in root.rglob("*.json")} == before


@pytest.mark.integration
@pytest.mark.parametrize("mode", ["mixed", "legacy_summary", "deterministic_failed"])
def test_report_view_keeps_latest_valid_record_despite_a_newer_invalid_one(tmp_path, mode):
    from backend.tests.test_audit_v3_c03_reports import _store
    storage, mid = _store(tmp_path)
    generation = storage.current_generation(mid).generationId
    _write_record(storage, mid, generation, "report_a", mode)
    _, chosen = _write_record(storage, mid, generation, "report_b", mode)
    invalid, bad = _write_record(storage, mid, generation, "report_z", mode)
    bad["createdAt"] = "2099-01-01T00:00:00+00:00"
    bad["payload"]["generationId"] = "foreign"
    bad.pop("contentDigest")
    bad["contentDigest"] = digest(bad)
    invalid.write_text(json.dumps(bad))
    before = invalid.read_bytes()
    view = ReportStore(storage).view(mid)
    assert view["reports"]["tactical_report"] == {**chosen, "status": "current"}
    assert view["notices"] == [
        {"taskType": "drills", "code": "REPORT_UNAVAILABLE_FOR_GENERATION"},
        {"taskType": "tactical_report", "code": "REPORT_VERIFICATION_REQUIRED"},
    ]
    assert invalid.read_bytes() == before


@pytest.mark.integration
def test_report_view_refuses_a_symlinked_member_even_when_its_target_is_valid(tmp_path):
    from backend.tests.test_audit_v3_c03_reports import _store
    storage, mid = _store(tmp_path)
    generation = storage.current_generation(mid).generationId
    real, chosen = _write_record(storage, mid, generation, "report_a")
    # A newer, otherwise valid record reachable only through a symlink must not be read.
    target = tmp_path / "outside" / "report_b.json"
    target.parent.mkdir()
    linked = _document("mixed", mid, generation, "report_b")
    linked["createdAt"] = "2099-01-01T00:00:00+00:00"
    linked["contentDigest"] = digest(linked)
    target.write_text(json.dumps(linked))
    (real.parent / "report_b.json").symlink_to(target)
    view = ReportStore(storage).view(mid)
    assert view["reports"]["tactical_report"] == {**chosen, "status": "current"}
    assert view["notices"] == [
        {"taskType": "drills", "code": "REPORT_UNAVAILABLE_FOR_GENERATION"},
        {"taskType": "tactical_report", "code": "REPORT_VERIFICATION_REQUIRED"},
    ]


@pytest.mark.integration
def test_report_view_only_isolates_expected_record_errors(tmp_path, monkeypatch):
    from backend.tests.test_audit_v3_c03_reports import _store
    storage, mid = _store(tmp_path)
    generation = storage.current_generation(mid).generationId
    record, _ = _write_record(storage, mid, generation)
    read_json = storage._read_json

    def unexpected(path):
        if path == record:
            raise RuntimeError("unexpected storage failure")
        return read_json(path)

    # Only malformed-record errors become notices; other failures still surface.
    monkeypatch.setattr(storage, "_read_json", unexpected)
    with pytest.raises(RuntimeError, match="unexpected storage failure"):
        ReportStore(storage).view(mid)
