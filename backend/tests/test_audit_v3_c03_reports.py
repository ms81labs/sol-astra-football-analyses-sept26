"""C03 R05/R06: source-bound reports; software fixtures, no model execution."""
from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.app.provider_gateway import ApprovedEvidencePackage, validate_output
from backend.app.storage import Storage
from backend.app.processor import process_match
from backend.app.schemas import MatchConfig
from backend.app.main import create_app

pytestmark = pytest.mark.integration
FIXTURE = Path(__file__).parent / 'fixtures' / 'sample_tracking.json'


def _package():
    return ApprovedEvidencePackage(match_id='match', generation_id='gen',
        evidence_ids=frozenset({'frame:0','event:current'}),
        metrics=({'metric':'possession_pct','value':1.0,'availability':'available',
                  'definitionVersion':'1','teamScope':'my_team','unit':'percent',
                  'intervalStart':0.0,'intervalEnd':10.0},), events=(), digest='fixture')


def _store(tmp_path):
    storage = Storage(tmp_path / 'store')
    match = storage.create_match('C03 fixture','tracking_json',FIXTURE.name,FIXTURE,MatchConfig())
    process_match(storage,storage.create_job(match.id).id)
    return storage,match.id


@pytest.mark.parametrize('raw',[
    {'evidence':['invented-without-prefix'],'summary':'Invented observation'},
    {'evidence':['frame:0','invented-without-prefix'],'summary':'Mixed references'},
    {'evidence':[{'matchId':'foreign','generationId':'gen','kind':'frame','localId':'0'}], 'summary':'Wrong match'},
    {'summary':'Factual claim without required evidence'},
    {'evidence':['frame:0'],'measurements':[{'metric':'possession_pct','value':True}]},
    {'evidence':['frame:0'],'measurements':[{'metric':'possession_pct','value':float('nan')}]},
])
def test_v3t24_26_false_grounding_regressions(raw):
    assert validate_output(raw,_package()).grounding != 'grounded'


def test_v3t22_accepted_state_published_inside_generation(tmp_path):
    storage,mid = _store(tmp_path)
    generation=storage.current_generation(mid)
    directory=storage.storage_root/'matches'/mid/'generations'/generation.generationId
    assert (directory/'accepted_match_state.json').is_file()


def test_v3t21_flat_narrative_not_current_export(tmp_path):
    storage,mid = _store(tmp_path)
    storage.save_analysis_artifact(mid,'tactical_report',{'summary':'FLAT_UNVERIFIED_SENTINEL','attacking':'OLD_UNVERIFIED_SENTINEL'})
    app=create_app(storage_root=storage.storage_root,run_jobs_inline=True)
    with TestClient(app,base_url='http://127.0.0.1') as client:
        response=client.get(f'/api/matches/{mid}/report/html')
    assert response.status_code == 200,response.text
    assert 'FLAT_UNVERIFIED_SENTINEL' not in response.text
    assert 'OLD_UNVERIFIED_SENTINEL' not in response.text
    assert (storage.storage_root/'matches'/mid/'tactical_report.json').exists()


def test_v3t23_missing_required_events_is_not_empty_success(tmp_path):
    storage,mid = _store(tmp_path)
    app=create_app(storage_root=storage.storage_root,run_jobs_inline=True)
    with TestClient(app,base_url='http://127.0.0.1') as client:
        gid=storage.current_generation(mid).generationId
        (storage.storage_root/'matches'/mid/'generations'/gid/'events.json').unlink()
        response=client.get(f'/api/matches/{mid}/report/html')
    assert response.status_code == 503,response.text

# Candidate-only acceptance extensions use the new explicit report schema.
import copy
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor

from backend.app.provider_gateway import ProviderGateway, ProviderBudgetLedger
from backend.app.report_store import ReportStore, StaleEvidenceGeneration, StaleReportPolicy
from backend.app.settings import ProcessingSettings
from backend.app.review_service import ReviewService


def _gateway(storage, adapter, settings=None):
    settings = settings or ProcessingSettings()
    return ProviderGateway(storage, settings, adapter_factory=lambda: adapter,
                           budget_ledger=ProviderBudgetLedger(storage.storage_root/'fake-provider-budget.sqlite3', 2.0))


def _draft(evidence, **changes):
    return {'schemaVersion':'report_draft_v1', 'matchId':evidence['matchId'],
            'generationId':evidence['generationId'], 'taskType':evidence.get('taskType') or 'tactical_report',
            **changes}


def _claim(metric):
    return {k:copy.deepcopy(metric[k]) for k in ('metric','definitionVersion','teamScope',
             'intervalStart','intervalEnd','unit','value','evidence')}


def _interprets(*args, **kwargs):
    return _draft(kwargs['approved_evidence'], interpretation='INTERPRETIVE_SENTINEL: review spacing.')


def _inventory(storage, mid):
    root=storage.generations.root(mid)
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*.json') if p.is_file() and 'reports' not in p.parts}


def test_v3t21_scoped_report_is_immutable_and_becomes_historical(tmp_path):
    storage,mid=_store(tmp_path)
    gateway=_gateway(storage,_interprets)
    original=storage.current_generation(mid).generationId
    before=_inventory(storage,mid)
    result=gateway.execute(mid,'tactical_report')
    assert result['grounding']=='interpretive'
    assert result['generationId']==original
    assert _inventory(storage,mid)==before # report does not rewrite generation/manifest/index
    ReviewService(storage).configure(mid,{'attackDirection':'right_to_left'})
    newer=storage.current_generation(mid).generationId
    assert newer!=original
    assert ReportStore(storage).view(mid)['reports']=={}
    old=ReportStore(storage).view(mid,generation_id=original)
    assert old['status']=='historical'
    assert old['reports']['tactical_report']['payload']['interpretation'].startswith('INTERPRETIVE_SENTINEL')
    reopened=Storage(storage.storage_root)
    assert ReportStore(reopened).view(mid,generation_id=original)['reports']==old['reports']
    app=create_app(storage_root=storage.storage_root,run_jobs_inline=True)
    with TestClient(app,base_url='http://127.0.0.1') as client:
        current=client.get(f'/api/matches/{mid}/report/html')
        historical=client.get(f'/api/matches/{mid}/report/html',params={'generationId':original})
        bundle=client.get(f'/api/matches/{mid}/export/match.json',params={'generationId':original})
        assert current.status_code==historical.status_code==bundle.status_code==200
        assert 'INTERPRETIVE_SENTINEL' not in current.text
        assert 'INTERPRETIVE_SENTINEL' in historical.text and 'historical' in historical.text
        assert current.headers['x-generation-id']==newer
        assert historical.headers['x-generation-id']==original
        assert bundle.json()['generationId']==original
        assert bundle.json()['acceptedMatchState']['generationId']==original
        assert bundle.json()['reports']['reports']['tactical_report']['generationId']==original
        for kind in ('metrics','frames','events'):
            csv=client.get(f'/api/matches/{mid}/export/{kind}.csv',params={'generationId':original})
            assert csv.status_code==200 and csv.headers['x-generation-id']==original


def test_v3t22_state_tracks_and_teams_follow_config_and_never_flat_override(tmp_path):
    storage,mid=_store(tmp_path)
    storage.submit_correction(mid,kind='team_mapping',payload={'swap':True},author='test')
    gid=storage.current_generation(mid).generationId
    storage.save_analysis_artifact(mid,'accepted_match_state',{'frames':[{'fake':'FLAT'}]})
    state=storage.load_accepted_match_state(mid)
    frames=storage.load_frames(mid)
    assert state['generationId']==gid and state['availability']=='available'
    identities={(p.id,team) for f in frames for team,players in [('my_team',f.myTeam),('enemy',f.enemies)] for p in players}
    assert len(state['frames'])==len(frames)
    for item in state['frames']:
        if item['controllingTrackId'] is not None:
            assert (item['controllingTrackId'],item['controllingTeam']) in identities
    assert storage.load_analysis_artifact(mid,'accepted_match_state')==state
    assert storage._read_json(storage.generations.root(mid)/'accepted_match_state.json')['frames']==[{'fake':'FLAT'}]


def test_v3t24_25_gateway_checks_every_reference_and_scoped_alias(tmp_path):
    storage,mid=_store(tmp_path)
    gateway=_gateway(storage,_interprets)
    gid=storage.current_generation(mid).generationId
    package,_=gateway.build_evidence(mid,gid,'tactical_report')
    alias=next(a for a,r in package.aliases.items() if r['kind']=='frame')
    ref=package.aliases[alias]
    for good in (alias,ref):
        raw=_draft({'matchId':mid,'generationId':gid}, observations=[{'text':'Observed frame; not semantic proof','evidence':[good]}])
        assert validate_output(raw,package).grounding=='referenced'
    bads=['invented', 'frame:0', 'event:invented', 0, None, True, [],
          {**ref,'matchId':'other'}, {**ref,'generationId':'other'}, {**ref,'localId':'missing'},
          {**ref,'kind':'invented'}, {**ref,'extra':'forged'}]
    for bad in bads:
        raw=_draft({'matchId':mid,'generationId':gid}, observations=[{'text':'Claim','evidence':[alias,bad]}])
        assert validate_output(raw,package).grounding=='validation_failed',bad
    # The same local frame ID under N+1 has a different permitted alias.
    ReviewService(storage).configure(mid,{'attackDirection':'right_to_left'})
    other,_=gateway.build_evidence(mid,storage.current_generation(mid).generationId,'tactical_report')
    assert alias not in other.aliases
    assert validate_output({'summary':'Claim','evidence':[alias]},other).grounding=='validation_failed'
    # User supplied IDs cannot extend the server-owned reference set.
    forged=_gateway(storage,lambda *a,**kw: {'summary':'Claim','evidence':['posted-id']}).execute(
        mid,'tactical_report',body={'knownEvidenceIds':['posted-id'],'events':[{'id':'posted-id'}]})
    assert forged['grounding']=='deterministic' and forged['validationDisposition']=='validation_failed'
    assert forged['metrics'] and forged['events'] is not None


def test_v3t26_exact_scope_numbers_availability_and_positive_controls(tmp_path):
    storage,mid=_store(tmp_path)
    gateway=_gateway(storage,_interprets)
    gid=storage.current_generation(mid).generationId
    package,_=gateway.build_evidence(mid,gid,'tactical_report')
    metric=next(m for m in package.metrics if m['availability'] in {'available','experimental'} and m['value'] is not None)
    good=_claim(metric)
    raw=_draft({'matchId':mid,'generationId':gid}, metricClaims=[good])
    valid=validate_output(raw,package)
    assert valid.grounding=='grounded'
    assert valid.payload['metricClaims'][0]['availability']==metric['availability']
    for field,value in [('teamScope','enemy' if good['teamScope']!='enemy' else 'my_team'),
        ('intervalStart',-1.0),('intervalEnd',good['intervalEnd']+1),('unit','invented'),
        ('definitionVersion','future'),('value',good['value']+1),('value',float('nan')),
        ('value',float('inf')),('value',True),('value','1.0')]:
        changed=copy.deepcopy(raw); changed['metricClaims'][0][field]=value
        assert validate_output(changed,package).grounding=='validation_failed',(field,value)
    for item in package.metrics:
        if item['availability'] in {'withheld','unknown'}:
            assert item['value'] is None and item['evidence']==[]
            forged={**_claim(item),'value':0.0,'evidence':[metric['evidence'][0]]}
            assert validate_output(_draft({'matchId':mid,'generationId':gid},metricClaims=[forged]),package).grounding=='validation_failed'
    # Genuine zero and experimental metadata are independent positive controls.
    from dataclasses import replace
    for availability in ('available','experimental'):
        zero={**metric,'value':0.0,'availability':availability}
        zero_package=replace(package,metrics=(zero,))
        output=validate_output(_draft({'matchId':mid,'generationId':gid},metricClaims=[_claim(zero)]),zero_package)
        assert output.grounding=='grounded' and output.payload['metricClaims'][0]['value']==0
        assert output.payload['metricClaims'][0]['availability']==availability
    pure=_draft({'matchId':mid,'generationId':gid},interpretation='Consider a spacing drill.')
    assert validate_output(pure,package).grounding=='interpretive'


@pytest.mark.parametrize('change',['generation','policy'])
def test_v3t27_blocking_provider_keeps_incurred_reservation_and_never_overwrites(tmp_path,change):
    storage,mid=_store(tmp_path)
    config=storage.get_match(mid).config.model_copy(deep=True)
    config.rights.cloudPermission=True; config.rights.processingScope='local_plus_burst'
    storage.update_match_config(mid,config)
    from backend.tests.provider_billing_fixtures import fake_spend_policy
    settings=ProcessingSettings(provider_spend_policy=fake_spend_policy(),cloud_provider_enabled=True,cloud_provider_api_key='test-only',
        cloud_model_id='test-model',allowed_model_ids=('test-model',),provider_call_reservation=0.25,provider_budget_limit=2.0)
    entered=threading.Event(); release=threading.Event(); calls=[]
    def adapter(*a,**kw):
        calls.append(kw); entered.set()
        assert release.wait(10),'test barrier was not released'
        return _interprets(*a,**kw)
    adapter.billing_contract_id = 'synthetic-byte-token-v1'
    gateway=_gateway(storage,adapter,settings)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(gateway.execute,mid,'tactical_report',requested_provider='cloud',body={'requireProvider':True})
        try:
            assert entered.wait(10),'provider was not reached'
            if change=='generation':
                ReviewService(storage).configure(mid,{'attackDirection':'right_to_left'})
            else:
                config.rights.cloudPermission=False
                storage.update_match_config(mid,config)
        finally:
            release.set()
        with pytest.raises(StaleEvidenceGeneration if change=='generation' else StaleReportPolicy):
            future.result(timeout=10)
    assert len(calls)==1
    assert gateway.budget_ledger.reservations()==[{'matchId':mid,'taskType':'tactical_report','amount':0.25}]
    assert ReportStore(storage).view(mid)['reports']=={}


def test_v3t27_actual_api_returns_typed_stale_without_a_second_call(tmp_path,monkeypatch):
    storage,mid=_store(tmp_path)
    calls=[]
    def adapter(*args,**kwargs):
        calls.append(1)
        ReviewService(storage).configure(mid,{'attackDirection':'right_to_left'})
        return _interprets(*args,**kwargs)
    monkeypatch.setattr('backend.app.main.run_analysis',adapter)
    with TestClient(create_app(storage_root=storage.storage_root,run_jobs_inline=True),base_url='http://127.0.0.1') as client:
        response=client.post(f'/api/matches/{mid}/analysis/tactical_report',json={'provider':'local'})
        assert response.status_code==409,response.text
        assert response.json()['error']=='STALE_EVIDENCE_GENERATION'
        assert calls==[1]
