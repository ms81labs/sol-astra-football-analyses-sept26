"""C03 acceptance: real snapshots/API/processes; synthetic observations, fake adapters."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import pytest
from backend.app.storage import Storage
from backend.tests.test_audit_v3_c01_generations import _child_setup, children as children

pytestmark = pytest.mark.integration


def _export_reader(root, mid, pipe):
    _child_setup()
    try:
        from backend.app.main import create_app
        from backend.app.report_export import build_match_report_export
        from backend.app.report_store import ReportStore
        from backend.app.match_bundle import build_match_bundle
        storage = Storage(Path(root))
        with storage.generation_snapshot(mid) as ref:
            pipe.send(('pinned', ref.generationId))
            assert pipe.recv() == 'read'
            bundle = build_match_bundle(storage, mid)
            summary, _, formations, shots = storage.load_analytics(mid)
            reports = ReportStore(storage).view(mid)
            html = build_match_report_export(match=storage.get_match(mid), summary=summary,
                formation_timeline=formations, shots=shots, events=storage.load_events(mid),
                tactical_report=reports['reports']['tactical_report']['payload'], drills=None,
                report_context=reports)
            pipe.send({'generationId': bundle['generationId'], 'stateGeneration': bundle['acceptedMatchState']['generationId'],
                       'playlistGeneration': bundle['playlist']['generationId'],
                       'reportGeneration': reports['generationId'], 'html': html,
                       'direction': bundle['match']['config']['attackDirection']})
    except BaseException as error:
        pipe.send(('error', repr(error)))
        raise
    finally:
        pipe.close()


def _advance(root, mid, pipe):
    _child_setup()
    try:
        from backend.app.review_service import ReviewService
        storage = Storage(Path(root))
        ReviewService(storage).configure(mid, {'attackDirection': 'right_to_left'})
        pipe.send(('published', storage.current_generation(mid).generationId))
    except BaseException as error:
        pipe.send(('error', repr(error)))
        raise
    finally:
        pipe.close()


def test_v3t23_actual_export_pin_survives_other_process_publication(tmp_path, children):
    from backend.tests.test_audit_v3_c03_reports import _store, _gateway, _interprets
    storage, mid = _store(tmp_path)
    old = storage.current_generation(mid).generationId
    _gateway(storage, _interprets).execute(mid, 'tactical_report')
    reader = children(_export_reader, str(storage.storage_root), mid)
    assert reader.receive() == ('pinned', old)
    writer = children(_advance, str(storage.storage_root), mid)
    kind, newer = writer.receive()
    assert kind == 'published' and newer != old
    writer.finish()  # no releasing the reader to let the writer pass
    reader.pipe.send('read')
    exported = reader.receive()
    reader.finish()
    assert {exported[k] for k in ('generationId','stateGeneration','playlistGeneration','reportGeneration')} == {old}
    assert 'INTERPRETIVE_SENTINEL' in exported['html'] and old in exported['html']
    assert exported['direction'] == 'left_to_right'


def test_v3t21_report_referencing_accepted_shot_is_omitted_after_rejection(tmp_path):
    from backend.app.main import create_app
    from backend.app.processor import process_match
    from backend.app.schemas import MatchConfig
    from backend.tests.test_audit_v3_c03_reports import _gateway, _draft
    from fastapi.testclient import TestClient
    rows = []
    for fid, ball_x in enumerate((91.,92.,50.,48.)):
        for entity, tid, x in [('ball',-1,ball_x),('my_team',9,90.),('enemy',4,10.)]:
            rows.append({'Frame_ID':fid,'Timestamp':fid*.2,'Entity_Type':entity,'Track_ID':tid,'X':x,'Y':34.,'Conf':.95})
    source=tmp_path/'shot.json';source.write_text(json.dumps(rows))
    storage = Storage(tmp_path / 'store')
    match = storage.create_match('Shot', 'tracking_json', source.name, source, MatchConfig())
    process_match(storage,storage.create_job(match.id).id)
    event=next(e for e in storage.load_events(match.id) if e.type=='shot')
    local_id=f'{event.frameId}:{event.type}:{event.timestamp}'
    storage.submit_correction(match.id,kind='event_accept',payload={'eventId':'event:'+local_id})
    old=storage.current_generation(match.id).generationId
    def adapter(*a,**kw):
        e=kw['approved_evidence'];ref=next(ref for ref in e['aliases'].values() if ref['kind']=='event' and ref['localId']==local_id)
        return _draft(e,observations=[{'text':'OLD_ACCEPTED_SHOT_SENTINEL','evidence':[ref]}])
    result=_gateway(storage,adapter).execute(match.id,'tactical_report')
    assert result['grounding']=='referenced'  # valid reference is not semantic proof
    raw_digest=hashlib.sha256(storage.get_match_input_path(match.id).read_bytes()).hexdigest()
    storage.submit_correction(match.id,kind='event_reject',payload={'eventId':'event:'+local_id})
    with TestClient(create_app(storage_root=storage.storage_root),base_url='http://127.0.0.1') as client:
        new=client.get(f'/api/matches/{match.id}/export/match.json').json()
        assert new['generationId']!=old and new['reports']['reports']=={}
        assert new['analytics']['shots']==[]
        assert next(e for e in new['events'] if e['type']=='shot')['reviewStatus']=='rejected'
        html=client.get(f'/api/matches/{match.id}/report/html')
        assert 'OLD_ACCEPTED_SHOT_SENTINEL' not in html.text
        oldhtml=client.get(f'/api/matches/{match.id}/report/html',params={'generationId':old})
        assert 'OLD_ACCEPTED_SHOT_SENTINEL' in oldhtml.text
        assert client.get(f'/api/matches/{match.id}/export/metrics.csv').headers['x-generation-id']==new['generationId']
    assert hashlib.sha256(storage.get_match_input_path(match.id).read_bytes()).hexdigest()==raw_digest


def test_v3t21_calibration_change_retains_but_does_not_reuse_old_report(tmp_path):
    from backend.tests.test_audit_v3_c02_projection import video, profile
    from backend.tests.test_audit_v3_c03_reports import _gateway, _interprets
    from backend.app.report_store import ReportStore
    storage=Storage(tmp_path/'store');mid=video(storage,tmp_path)
    storage.commit_calibration_for_match(mid,profile().model_dump(mode='json'))
    result=_gateway(storage,_interprets).execute(mid,'tactical_report')
    storage.commit_calibration_for_match(mid,profile(dx=5.).model_dump(mode='json'))
    assert ReportStore(storage).view(mid)['reports']=={}
    assert ReportStore(storage).view(mid,generation_id=result['generationId'])['status']=='historical'


def test_v3t24_gateway_accepts_scoped_metric_and_interpretation_without_factual_promotion(tmp_path):
    from backend.tests.test_audit_v3_c03_reports import _store,_gateway,_draft,_claim
    from backend.app.report_store import ReportStore
    storage,mid=_store(tmp_path)
    def measured(*a,**kw):
        e=kw['approved_evidence'];metric=next(m for m in e['metrics'] if m['value'] is not None)
        return _draft(e,metricClaims=[_claim(metric)])
    good=_gateway(storage,measured).execute(mid,'tactical_report')
    assert good['grounding']=='grounded' and good['metricClaims'][0]['grounding']=='grounded'
    assert good['metricClaims'][0]['evidence'][0]['generationId']==good['generationId']
    record=ReportStore(storage).view(mid)['reports']['tactical_report']
    assert record['inputEvidenceDigest']==good['inputEvidenceDigest']
    assert record['outputSchema']=='report_draft_v1' and record['promptVersion']


def test_v3t22_missing_required_accepted_state_is_not_empty_available(tmp_path):
    from backend.tests.test_audit_v3_c03_reports import _store
    from backend.app.main import create_app
    from fastapi.testclient import TestClient
    storage,mid=_store(tmp_path)
    with TestClient(create_app(storage_root=storage.storage_root),base_url='http://127.0.0.1') as client:
        gid=storage.current_generation(mid).generationId
        (storage.generations.root(mid)/'generations'/gid/'accepted_match_state.json').unlink()
        assert client.get(f'/api/matches/{mid}/export/match.json').status_code==503


def test_v3t21_report_integrity_failure_does_not_fall_back_to_flat_legacy(tmp_path):
    from backend.tests.test_audit_v3_c03_reports import _store,_gateway,_interprets
    from backend.app.report_store import ReportStore
    storage,mid=_store(tmp_path);result=_gateway(storage,_interprets).execute(mid,'tactical_report')
    report=storage.generations.root(mid)/'reports'/result['generationId']/'tactical_report'/f"{result['reportId']}.json"
    raw=json.loads(report.read_text());raw['payload']['interpretation']='TAMPERED';report.write_text(json.dumps(raw))
    storage.save_analysis_artifact(mid,'tactical_report',{'summary':'FLAT'})
    before=report.read_bytes();view=ReportStore(storage).view(mid)
    assert view['reports']=={}
    assert any(n['code']=='REPORT_VERIFICATION_REQUIRED' for n in view['notices'])
    assert report.read_bytes()==before


def test_v3t21_report_and_playlist_generations_are_retention_protected(tmp_path):
    from backend.tests.test_audit_v3_c03_reports import _store,_gateway,_interprets
    from backend.app.schemas import ReviewBundleItem
    from backend.app.review_service import ReviewService
    storage,mid=_store(tmp_path);old=storage.current_generation(mid).generationId
    report=_gateway(storage,_interprets).execute(mid,'tactical_report')
    ReviewService(storage).configure(mid,{'attackDirection':'right_to_left'})
    playlist_generation=storage.current_generation(mid).generationId
    item=ReviewBundleItem(annotationId='note',matchId=mid,frameStart=0,frameEnd=1,timestampStart=0,timestampEnd=.1,label='Reviewed')
    bundle=storage.create_review_bundle('Selection',items=[item])
    assert bundle.items[0].generationId==playlist_generation
    assert bundle.items[0].sourceStatus=='generation_bound'
    ReviewService(storage).configure(mid,{'attackDirection':'left_to_right'})
    ReviewService(storage).configure(mid,{'attackDirection':'right_to_left'})
    plan=storage.generations.retention(mid)
    assert old in plan['protected'] and playlist_generation in plan['protected']
    assert storage.get_review_bundle(bundle.id).items[0].generationId==playlist_generation
    assert report['generationId']==old


def test_v3t21_playlist_commands_resolve_only_inside_selected_generation(tmp_path):
    from backend.tests.test_audit_v3_c03_reports import _store
    storage,mid=_store(tmp_path);old=storage.current_generation(mid).generationId
    command=storage.submit_correction(mid,kind='playlist_item',payload={'timestampStart':0.,'timestampEnd':.1})
    new=storage.current_generation(mid).generationId
    assert storage.edit_list_for_match(mid)['intervals']==[(0.,.1)]
    assert storage.edit_list_for_match(mid,generation_id=old)['intervals']==[]
    storage.undo_correction(mid,command.correctionId)
    assert storage.edit_list_for_match(mid)['intervals']==[]
    assert storage.edit_list_for_match(mid,generation_id=new)['intervals']==[(0.,.1)]


def test_v3t26_actual_approved_zero_sprints_is_a_valid_grounded_number(tmp_path):
    from backend.tests.test_audit_v3_c02_identity import tracking
    from backend.tests.test_audit_v3_c03_reports import _gateway,_draft,_claim
    storage=Storage(tmp_path/'store');mid=tracking(storage,tmp_path)
    storage.promote_identity_for_match(mid,{'reviewed':True})
    def measured(*a,**kw):
        e=kw['approved_evidence'];metric=next(m for m in e['metrics'] if m['metric']=='my_team_sprints')
        assert metric['availability']=='available' and metric['value']==0
        return _draft(e,metricClaims=[_claim(metric)])
    result=_gateway(storage,measured).execute(mid,'tactical_report')
    assert result['metricClaims'][0]['value']==0 and result['grounding']=='grounded'


@pytest.mark.parametrize('bad',[0, True, None, [], 'not-a-claim'])
def test_v3t24_malformed_metric_objects_reject_without_validator_crash(tmp_path,bad):
    from backend.tests.test_audit_v3_c03_reports import _package
    from backend.app.provider_gateway import validate_output
    assert validate_output({'measurements':[bad]},_package()).grounding=='validation_failed'


def test_v3t24_real_llm_adapter_keeps_scoped_schema_and_prompt_without_network(tmp_path,monkeypatch):
    from backend.tests.test_audit_v3_c03_reports import _store,_gateway
    from backend.app import llm
    from backend.app.report_store import ReportStore
    from backend.app.provider_adapters import LOCAL_MODEL_ID
    storage,mid=_store(tmp_path)
    gid=storage.current_generation(mid).generationId
    calls=[]
    def fake_execute(prompt,task,validate,**kwargs):
        calls.append(prompt)
        assert gid in prompt and 'approved' in prompt.lower()
        return validate(task,{'schemaVersion':'report_draft_v1','matchId':mid,'generationId':gid,
            'taskType':'drills','interpretation':'Consider a spacing drill.',
            'drills':[{'name':'Spacing','objective':'Review shape','setup':'Small-sided drill','duration':'10 min'}]})
    monkeypatch.setattr(llm,'execute_local',fake_execute)
    response=_gateway(storage,llm.run_analysis).execute(mid,'drills')
    assert len(calls)==1 and response['grounding']=='interpretive'
    assert response['drills'][0]['name']=='Spacing'
    assert ReportStore(storage).view(mid)['reports']['drills']['modelId']==LOCAL_MODEL_ID


def test_v3t25_two_matches_identical_local_ids_cannot_share_reference(tmp_path):
    from backend.tests.test_audit_v3_c03_reports import _store,_gateway,_interprets
    from backend.app.provider_gateway import validate_output
    storage,mid=_store(tmp_path)
    other,mid2=_store(tmp_path/'second')
    p1,_=_gateway(storage,_interprets).build_evidence(mid,storage.current_generation(mid).generationId,'tactical_report')
    p2,_=_gateway(other,_interprets).build_evidence(mid2,other.current_generation(mid2).generationId,'tactical_report')
    ref=next(r for r in p1.aliases.values() if r['kind']=='frame')
    assert any(r['localId']==ref['localId'] for r in p2.aliases.values() if r['kind']=='frame')
    assert validate_output({'summary':'Foreign reference','evidence':[ref]},p2).grounding=='validation_failed'


def test_v3t22_legacy_state_unknown_without_overwriting_or_importing_flat_claim(tmp_path):
    from backend.tests.test_audit_v3_c03_reports import _store
    from backend.app.accepted_state import bind_state
    storage,mid=_store(tmp_path)
    state=storage.load_accepted_match_state(mid)
    assert state['availability']=='available'
    # A snapshot without an accepted-state argument is explicitly unknown, not
    # inferred from a newer mutable flat diagnostic file.
    storage.save_analysis_artifact(mid,'accepted_match_state',{'frames':[{'forged':'do-not-import'}]})
    frames=storage.load_frames(mid); summary, assignments, formations, shots=storage.load_analytics(mid)
    ref=storage.publish_generation(mid,frames=frames,summary=summary,assignments=assignments,
        formation_timeline=formations,shots=shots,events=storage.load_events(mid),correction_head='none')
    assert storage.load_accepted_match_state(mid)==bind_state(mid,ref.generationId,None)
    assert storage._read_json(storage.generations.root(mid)/'accepted_match_state.json')['frames']==[{'forged':'do-not-import'}]
