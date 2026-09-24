"""C02 R04: approval binds revision, coverage and scope, never just a verb."""
from __future__ import annotations
import json
import pytest
from backend.app.semantic_commands import SemanticCommandError
from backend.app.schemas import MatchConfig
from backend.app.storage import Storage
from backend.app.processor import process_match
from backend.tests.test_audit_v3_c02_projection import profile

pytestmark = pytest.mark.integration


def tracking(storage, tmp_path):
    source=tmp_path/'tracking.json'
    source.write_text(json.dumps([{'frameId':f,'timestamp':f/5,
        'myTeam':[{'id':7,'x':12.+f,'y':30.,'confidence':.9}],
        'enemies':[{'id':18,'x':80.-f,'y':40.,'confidence':.9}],
        'ball':{'x':12.+f,'y':30.,'confidence':.9}} for f in range(10)]))
    m=storage.create_match('Identity synthetic','tracking_json',source.name,source,
        MatchConfig(pitchLengthM=100.,pitchWidthM=60.))
    process_match(storage,storage.create_job(m.id).id)
    assert storage.commit_calibration_for_match(m.id,profile().model_dump(mode='json'))['committed']
    return m.id


def physical(storage,mid):
    return [m for m in storage.load_analytics(mid)[0].metricAvailability
            if m.metric in {'my_team_distance_m','enemy_distance_m','my_team_top_speed_kmh'}]


def test_v3t19_split_invalidates_earlier_approval_everywhere(tmp_path):
    s=Storage(tmp_path/'store');mid=tracking(s,tmp_path)
    s.promote_identity_for_match(mid,{'reviewed':True})
    assert all(m.availability=='available' for m in physical(s,mid))
    s.submit_correction(mid,kind='track_split',payload={'trackId':'7','atFrame':5,'newTrackId':99})
    assert all(m.availability=='withheld' and m.value is None for m in physical(s,mid))
    assert s._stored_identity_continuous(mid) is False
    assert s.player_observations_for_match(mid)['totalsWithheld'] is True
    assert s.derived_distance_for_match(mid)['availability']=='withheld'
    s.promote_identity_for_match(mid,{'reviewed':True})
    assert all(m.availability=='available' for m in physical(s,mid))


@pytest.mark.parametrize('partial',[{'trackIds':['7']},{'intervalStart':0.,'intervalEnd':.6},{'teamScope':'my_team'}])
def test_v3t19_partial_review_never_certifies_full_match(tmp_path,partial):
    s=Storage(tmp_path/'store');mid=tracking(s,tmp_path)
    s.promote_identity_for_match(mid,{'reviewed':True,**partial})
    assert s._stored_identity_continuous(mid) is False
    assert all(m.availability=='withheld' for m in physical(s,mid))
    assert s.player_observations_for_match(mid)['totalsWithheld'] is True
    assert s.derived_distance_for_match(mid)['availability']=='withheld'


def test_revision_and_approval_survive_metadata_but_not_undo_edit(tmp_path):
    s=Storage(tmp_path/'store');mid=tracking(s,tmp_path)
    s.promote_identity_for_match(mid,{'reviewed':True})
    first=s.identity_eligibility(mid)
    config=s.get_match(mid).config.model_copy(update={'homeTeam':'New title'})
    s.update_match_config(mid,config)
    assert s.identity_eligibility(mid)==first
    split=s.submit_correction(mid,kind='track_split',payload={'trackId':'7','atFrame':5,'newTrackId':99})
    assert s.identity_eligibility(mid)['identityRevision']!=first['identityRevision']
    s.undo_correction(mid,split.correctionId)
    assert s._stored_identity_continuous(mid) is False
    s.promote_identity_for_match(mid,{'reviewed':True})
    assert s._stored_identity_continuous(mid) is True
    # Canonical steps are metres once, not homography applied to normalised positions.
    assert s.derived_distance_for_match(mid)['value']==pytest.approx(18.)


def test_old_pinned_generation_uses_its_own_approval(tmp_path):
    s=Storage(tmp_path/'store');mid=tracking(s,tmp_path)
    s.promote_identity_for_match(mid,{'reviewed':True})
    old=s.current_generation(mid).generationId
    s.submit_correction(mid,kind='track_split',payload={'trackId':'7','atFrame':5,'newTrackId':99})
    assert s._stored_identity_continuous(mid) is False
    with s.generation_snapshot(mid,generation_id=old):
        assert s._stored_identity_continuous(mid) is True
        assert s.player_observations_for_match(mid)['totalsWithheld'] is False


@pytest.mark.parametrize('bad',[{'identityRevision':'stale'},{'trackIds':['ghost']},
                              {'intervalStart':True,'intervalEnd':1.}, {'intervalStart':2.,'intervalEnd':1.}])
def test_bad_identity_approval_rejected_before_log_or_generation(tmp_path,bad):
    s=Storage(tmp_path/'store');mid=tracking(s,tmp_path)
    old=(s.current_generation(mid).generationId,s.list_corrections(mid))
    with pytest.raises(SemanticCommandError):
        s.promote_identity_for_match(mid,{'reviewed':True,**bad})
    assert (s.current_generation(mid).generationId,s.list_corrections(mid))==old


@pytest.mark.parametrize('view',['report','players','distance'])
def test_one_reader_keeps_old_identity_eligibility_while_another_publishes(tmp_path,monkeypatch,view):
    s=Storage(tmp_path/'store');mid=tracking(s,tmp_path)
    s.promote_identity_for_match(mid,{'reviewed':True})
    other=Storage(s.storage_root)
    old=s.current_generation(mid).generationId
    original=s.load_frames
    advanced=False
    def advancing(*args,**kwargs):
        nonlocal advanced
        frames=original(*args,**kwargs)
        if not advanced:
            advanced=True
            other.submit_correction(mid,kind='track_split',payload={'trackId':'7','atFrame':5,'newTrackId':99})
        return frames
    monkeypatch.setattr(s,'load_frames',advancing)
    if view=='report':
        result=s.assemble_match_report(mid)
        physical_metrics=[m for m in result['factPackage']['metrics'] if m['metric']=='my_team_distance_m']
        assert physical_metrics and physical_metrics[0]['availability']=='available'
    elif view=='players':
        assert s.player_observations_for_match(mid)['totalsWithheld'] is False
    else:
        assert s.derived_distance_for_match(mid)['availability']=='available'
    assert advanced and other.current_generation(mid).generationId!=old
    assert other.identity_eligibility(mid)['continuous'] is False


def test_scoped_api_reads_select_one_generation_after_new_edit(tmp_path):
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    app=create_app(storage_root=tmp_path/'store');s=app.state.storage;mid=tracking(s,tmp_path)
    s.promote_identity_for_match(mid,{'reviewed':True})
    old=s.current_generation(mid).generationId
    s.submit_correction(mid,kind='track_split',payload={'trackId':'7','atFrame':5,'newTrackId':99})
    with TestClient(app,base_url='http://127.0.0.1') as client:
        current=client.get(f'/api/matches/{mid}').json()['generationId']
        assert current!=old
        for suffix in ['', '/frames', '/analytics', '/events', '/evidence', '/metrics', '/heatmap', '/players', '/formation', '/geometry/distance']:
            response=client.get(f'/api/matches/{mid}{suffix}',params={'generationId':old})
            assert response.status_code==200,response.text
            assert response.json()['generationId']==old
        assert client.get(f'/api/matches/{mid}/players',params={'generationId':old}).json()['totalsWithheld'] is False
        assert client.get(f'/api/matches/{mid}/players').json()['totalsWithheld'] is True


@pytest.mark.parametrize('context',[None,{}, {'schemaVersion':1,'approvals':[None]},
    {'schemaVersion':1,'identityRevision':'identity_'+'a'*64,'observationDigest':'b'*64,
     'requiredScope':{'intervalStart':0.,'intervalEnd':1.,'trackIds':['7']},'approvals':['invalid']},
    {'schemaVersion':1,'identityRevision':'identity_'+'a'*64,'observationDigest':'b'*64,
     'requiredScope':{'intervalStart':0.,'intervalEnd':float('nan'),'trackIds':['7']},'approvals':[]}])
def test_malformed_or_unscoped_approval_never_certifies_identity(context):
    from backend.app.identity_eligibility import identity_eligibility
    assert identity_eligibility(context)['continuous'] is False


@pytest.mark.parametrize('timestamps', [[0.0], [0.0, 2.0]])
def test_physical_views_agree_when_no_movement_interval_is_eligible(tmp_path, timestamps):
    s = Storage(tmp_path / 'store')
    source = tmp_path / 'time-limited.json'
    source.write_text(json.dumps([
        {'frameId': i, 'timestamp': timestamp,
         'myTeam': [{'id': 7, 'x': 12. + i, 'y': 30., 'confidence': .9}]}
        for i, timestamp in enumerate(timestamps)
    ]))
    m = s.create_match('Time limited', 'tracking_json', source.name, source,
                       MatchConfig(pitchLengthM=100., pitchWidthM=60.))
    process_match(s, s.create_job(m.id).id)
    s.commit_calibration_for_match(m.id, profile().model_dump(mode='json'))
    s.promote_identity_for_match(m.id, {'reviewed': True})
    # The identity review remains recorded, but it cannot manufacture a measured
    # movement interval or bridge the distance endpoint's existing cut rule.
    assert s._stored_identity_continuous(m.id) is True
    assert all(metric.availability == 'withheld' and metric.value is None
               for metric in physical(s, m.id))
    assert s.player_observations_for_match(m.id)['totalsWithheld'] is True
    assert s.derived_distance_for_match(m.id)['availability'] == 'withheld'
    assert s.load_analytics(m.id)[0].myTeamDistance is None
    report = s.assemble_match_report(m.id)
    assert all(metric['value'] is None for metric in report['factPackage']['metrics']
               if metric['metric'] in {'my_team_distance_m', 'enemy_distance_m'})
