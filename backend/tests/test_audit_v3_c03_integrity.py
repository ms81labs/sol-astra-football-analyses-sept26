"""C03 persisted report schema, optional-state isolation and alias ambiguity."""
from __future__ import annotations
import copy
import json
import pytest
from backend.app.report_contracts import digest
from backend.app.report_store import ReportStore
from backend.tests.test_audit_v3_c03_reports import _store, _gateway, _interprets

pytestmark = pytest.mark.integration


@pytest.mark.parametrize('change', ['missing_date','bad_date','payload_scope','bad_schema','bad_claim','bad_disposition'])
def test_persisted_report_schema_failure_is_visible_without_mutating(change, tmp_path):
    storage, mid = _store(tmp_path)
    result = _gateway(storage, _interprets).execute(mid, 'tactical_report')
    path = storage.generations.root(mid)/'reports'/result['generationId']/'tactical_report'/f"{result['reportId']}.json"
    raw = json.loads(path.read_text())
    if change == 'missing_date': raw.pop('createdAt')
    elif change == 'bad_date': raw['createdAt'] = 'not-a-timestamp'
    elif change == 'payload_scope': raw['payload']['generationId'] = 'foreign'
    elif change == 'bad_schema': raw['outputSchema'] = 'unknown_v99'
    elif change == 'bad_claim': raw['payload']['observations'] = [None]
    elif change == 'bad_disposition': raw['validationDisposition'] = 'approved'
    # A valid checksum is not a substitute for a well-formed scoped envelope.
    raw.pop('contentDigest'); raw['contentDigest'] = digest(raw)
    path.write_text(json.dumps(raw)); before = path.read_bytes()
    view = ReportStore(storage).view(mid)
    assert view['reports'] == {}
    assert any(n['code'] == 'REPORT_VERIFICATION_REQUIRED' for n in view['notices'])
    assert path.read_bytes() == before


def test_fallback_record_identifies_its_actual_schema(tmp_path):
    storage, mid = _store(tmp_path)
    result = _gateway(storage, lambda *a, **kw: {'summary': 'Unreferenced claim'}).execute(mid, 'drills')
    record = ReportStore(storage).view(mid)['reports']['drills']
    assert record['outputSchema'] == result['schemaVersion'] == 'deterministic_report_v1'
    assert record['validationDisposition'] == 'validation_failed'
    assert record['payload']['metrics']


def test_duplicate_local_evidence_ids_refuse_before_dispatch(tmp_path):
    from backend.app.schemas import DetectedEvent
    from backend.app.provider_gateway import ProviderDenied
    storage, mid = _store(tmp_path)
    event = DetectedEvent(type='pass', frameId=0, timestamp=0., team='my_team', fromTrackId=1, toTrackId=2,
                          description='First observation', eventId='a')
    another = event.model_copy(update={'eventId': 'b', 'description': 'Different observation', 'toTrackId': 3})
    storage.save_events(mid, [event, another])
    calls=[]
    def adapter(*a, **kw):
        calls.append(kw)
        return _interprets(*a, **kw)
    with pytest.raises(ProviderDenied, match='AMBIGUOUS_EVIDENCE_IDS'):
        _gateway(storage, adapter).execute(mid, 'tactical_report')
    assert not calls
    assert not (storage.generations.root(mid)/'reports').exists()


def test_missing_generation_pointer_never_exposes_flat_accepted_state(tmp_path):
    from backend.app.generations import GenerationRecoveryRequired
    storage, mid = _store(tmp_path)
    storage.save_analysis_artifact(mid,'accepted_match_state',{'frames':[{'legacy':'not bound'}]})
    flat=storage.generations.root(mid)/'accepted_match_state.json'; before=flat.read_bytes()
    (storage.generations.root(mid)/'current_generation.json').unlink()
    with pytest.raises(GenerationRecoveryRequired): storage.load_analysis_artifact(mid,'accepted_match_state')
    assert flat.read_bytes()==before


def test_benchmark_snapshot_get_never_reprocesses_or_advances_generation(tmp_path, monkeypatch):
    from backend.app.main import create_app
    from fastapi.testclient import TestClient
    from backend.tests.test_audit_v3_c03_reports import _inventory
    storage, mid = _store(tmp_path)
    def forbidden(*a, **kw): raise AssertionError("GET must not reprocess or write live cluster settings")
    monkeypatch.setattr('backend.app.run_benchmarks.probe_selected_cluster_benchmarks', forbidden)
    with TestClient(create_app(storage_root=storage.storage_root),base_url='http://127.0.0.1') as client:
        before=_inventory(storage,mid)
        g=storage.current_generation(mid).generationId
        for _ in range(2):
            response=client.get(f'/api/matches/{mid}/benchmark',params={'generationId':g,'includeSelectedClusterProbe':True})
            assert response.status_code==200,response.text
            assert response.json()['generationId']==g and response.json()['probeStatus']=='not_run'
            assert response.json()['recommendedCluster'] is None
        assert _inventory(storage,mid)==before


def test_evidence_digest_binds_the_exact_sampled_observations_passed_to_adapter(tmp_path):
    storage, mid = _store(tmp_path)
    received = []
    def adapter(*a, **kw):
        package = kw['approved_evidence']
        received.append(copy.deepcopy(package))
        assert package['frameSamples']
        actual = {name: package[name] for name in ('matchId','generationId','taskType','aliases','metrics','events','frameSamples')}
        assert digest(actual) == package['inputEvidenceDigest']
        changed = copy.deepcopy(actual)
        changed['frameSamples'][0]['timestamp'] += 1.
        assert digest(changed) != package['inputEvidenceDigest']
        return _interprets(*a, **kw)
    result = _gateway(storage, adapter).execute(mid, 'tactical_report')
    assert len(received) == 1
    assert ReportStore(storage).view(mid)['reports']['tactical_report']['inputEvidenceDigest'] == result['inputEvidenceDigest']
