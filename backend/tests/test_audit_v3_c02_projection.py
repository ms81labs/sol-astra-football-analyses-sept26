"""C02 R03: actual source-coordinate materialisation, not detector accuracy."""
from __future__ import annotations
import hashlib
import json

import pytest
from backend.app.processor import reprocess_video_match
from backend.app.schemas import MatchConfig, ColorClusterSummary
from backend.app.storage import Storage
from backend.app.workbench.geometry import CalibrationProfile, Landmark, commit_calibration

pytestmark = pytest.mark.integration


def profile(dx=0.0, sx=0.1, **kwargs):
    # These are independent, synthetic holdouts, not fit points relabelled as holdouts.
    expected = [(10.,10.),(90.,10.),(10.,50.),(90.,50.)]
    return CalibrationProfile(calibrationId=f'synthetic-{dx}-{sx}', cameraModel='planar_homography',
        cameraSide='touchline_north', pitchLengthM=100., pitchWidthM=60.,
        homography=[[sx,0.,dx],[0.,.1,0.],[0.,0.,1.]],
        landmarks=[Landmark(name=f'holdout-{i}',imageX=x/.1,imageY=y/.1,
            pitchX=x*(sx/.1)+dx,pitchY=y,independentHoldout=True)
            for i,(x,y) in enumerate(expected)], **kwargs)


def video(storage, tmp_path, *, with_source=True, prepare_rows=None):
    source=tmp_path/'synthetic-video.mp4';source.write_bytes(b'not decoded - synthetic post-perception observations')
    match=storage.create_match('Synthetic pixels','video',source.name,source,
        MatchConfig(myTeamCluster=0,pitchLengthM=100.,pitchWidthM=60.))
    rows=[]
    for fid in range(5):
        row={'Frame_ID':fid,'Timestamp':fid/25,'PTS':fid,'TimeBaseNum':1,'TimeBaseDen':25,
             'Entity_Type':'player','Track_ID':7,'X':9.,'Y':9.,'Conf':.9}
        if with_source:
            row.update(Source_X1=100.+fid*10,Source_Y1=100.,Source_X2=140.+fid*10,Source_Y2=180.,
                       Source_Width=1000,Source_Height=600)
        rows.append(row)
    if prepare_rows is not None:
        prepare_rows(rows)
    storage.save_raw_rows(match.id,rows)
    storage.update_match_status(match.id,status='ready',team_clusters=[
        ColorClusterSummary(clusterId=0,rgbCentroid=[255.,0.,0.],trackIds=[7])])
    reprocess_video_match(storage,match.id)
    return match.id


def coords(storage,mid):
    return [(f.myTeam[0].x,f.myTeam[0].y) for f in storage.load_frames(mid)]


def test_v3t16_video_reprojection_uses_bottom_centre_and_preserves_source(tmp_path,monkeypatch):
    storage=Storage(tmp_path/'store');mid=video(storage,tmp_path)
    import backend.app.processor as proc
    monkeypatch.setattr(proc,'process_video_input',lambda *a,**k:pytest.fail('Detector was invoked'))
    raw=storage._match_dir(mid)/'raw_rows.json';before=hashlib.sha256(raw.read_bytes()).hexdigest()
    for dx,sx,expected in [(0.,.1,(12.,30.)),(5.,.1,(17.,30.)),(0.,.11,(13.2,30.))]:
        calibration=profile(dx,sx)
        assert commit_calibration(calibration)['committed']
        result=storage.commit_calibration_for_match(mid,calibration.model_dump(mode='json'))
        assert result['committed']
        assert coords(storage,mid)[0]==pytest.approx(expected)
        assert coords(storage,mid)[1][0]-coords(storage,mid)[0][0]==pytest.approx(10*sx)
        assert storage.current_generation(mid).calibrationRevision==storage.calibration_revision(mid).revisionId
        assert hashlib.sha256(raw.read_bytes()).hexdigest()==before
    reopened=Storage(storage.storage_root)
    assert coords(reopened,mid)[0]==pytest.approx((13.2,30.))


def test_v3t18_missing_source_cannot_publish_false_recalibration(tmp_path):
    storage=Storage(tmp_path/'store');mid=video(storage,tmp_path,with_source=False)
    before=storage.current_generation(mid).generationId
    with pytest.raises(Exception) as error:
        storage.commit_calibration_for_match(mid,profile().model_dump(mode='json'))
    assert 'source' in str(error.value).lower()
    assert storage.current_generation(mid).generationId==before
    assert storage.calibration_revision(mid) is None


def envelope(space, *, positions=(12.,30.), **coordinates):
    return {'format':'guerilla_tracking_v2','schemaVersion':2,
        'coordinates':{'space':space,**coordinates},
        'frames':[{'frameId':0,'timestamp':0.,'myTeam':[{'id':7,'x':positions[0],'y':positions[1]}]},
                  {'frameId':1,'timestamp':.2,'myTeam':[{'id':7,'x':positions[0]+1,'y':positions[1]}]}]}


@pytest.mark.parametrize('space,position,extra',[
    ('source_pixels',(120.,180.),{'sourceWidth':1000,'sourceHeight':600,'streamId':'video:0'}),
    ('pitch_metres',(12.,18.),{'pitchLengthM':100.,'pitchWidthM':60.}),
    ('pitch_normalized_0_100',(12.,30.),{}),
])
def test_v3t17_declared_tracking_is_projected_exactly_once_on_initial_and_rebuild(tmp_path,space,position,extra):
    from backend.app.processor import process_match
    from backend.app.review_service import ReviewService
    s=Storage(tmp_path/'store');path=tmp_path/'declared.json'
    path.write_text(json.dumps(envelope(space,positions=position,**extra)))
    before=path.read_bytes()
    m=s.create_match('Declared','tracking_json',path.name,path,MatchConfig(pitchLengthM=100.,pitchWidthM=60.))
    assert s.commit_calibration_for_match(m.id,profile().model_dump(mode='json'))['committed']
    process_match(s,s.create_job(m.id).id)
    assert coords(s,m.id)[0]==pytest.approx((12.,30.))
    ReviewService(s).rebuild_generation(m.id,reason='calibration')
    assert coords(s,m.id)[0]==pytest.approx((12.,30.))
    assert path.read_bytes()==before
    f=s.load_frames(m.id)[0]
    assert f.coordinateSpace=='pitch_normalized_0_100' and f.geometryAvailable
    assert f.coordinateProvenance['inputConvention']['space']==space


def test_v3t17_unknown_input_is_not_inferred_from_small_numbers(tmp_path):
    from backend.app.processor import process_match
    s=Storage(tmp_path/'store');path=tmp_path/'unknown.json'
    path.write_text(json.dumps(envelope('unknown')))
    m=s.create_match('Unknown','tracking_json',path.name,path,MatchConfig())
    with pytest.raises(Exception) as error:
        process_match(s,s.create_job(m.id).id)
    assert getattr(error.value,'code',None)=='COORDINATE_CONVENTION_REQUIRED'
    assert not (s.generations.root(m.id)/'current_generation.json').exists()


def test_v3t17_named_legacy_format_has_explicit_migration_provenance(tmp_path):
    from backend.app.processor import process_match
    s=Storage(tmp_path/'store');path=tmp_path/'legacy.json'
    # Values outside 0..100 are not used to silently change the convention.
    path.write_text(json.dumps(envelope('pitch_normalized_0_100',positions=(110.,-10.))['frames']))
    m=s.create_match('Legacy','tracking_json',path.name,path,MatchConfig())
    process_match(s,s.create_job(m.id).id)
    f=s.load_frames(m.id)[0]
    assert (f.myTeam[0].x,f.myTeam[0].y)==(110.,-10.)
    assert f.coordinateProvenance['migration']=='guerilla_frame_or_rows_v1:normalised_pitch'


@pytest.mark.parametrize('matrix,box',[
    ([[2.,0.,50.],[0.,2.,20.],[0.,0.,1.]],[25.,40.,45.,80.]),
    ([[0.,1.,0.],[-1.,0.,600.],[0.,0.,1.]],[420.,100.,500.,140.]),
])
def test_v3t16_crop_resize_rotation_inverted_before_ground_contact(tmp_path,matrix,box):
    from backend.app.coordinate_contracts import CoordinateConvention
    def prepare(rows):
        for row in rows:
            for k in ('Source_X1','Source_Y1','Source_X2','Source_Y2'):
                row.pop(k)
            row['bbox']=box
    s=Storage(tmp_path/'store');mid=video(s,tmp_path,prepare_rows=prepare)
    c=s.get_match(mid).config.model_copy(update={'coordinateConvention':CoordinateConvention(
        space='source_pixels',sourceWidth=1000,sourceHeight=600,streamId='video:0',sourceFromObservation=matrix)})
    # Use the actual analytical command boundary before calibration exists.
    reprocess_video_match(s,mid,config=c)
    before=(s.generations.root(mid)/'raw_rows.json').read_bytes()
    s.commit_calibration_for_match(mid,profile().model_dump(mode='json'))
    assert coords(s,mid)[0]==pytest.approx((12.,30.))
    assert (s.generations.root(mid)/'raw_rows.json').read_bytes()==before


def test_calibration_interval_does_not_extend_to_uncovered_frames(tmp_path):
    s=Storage(tmp_path/'store');mid=video(s,tmp_path)
    s.commit_calibration_for_match(mid,profile(sourceIntervalEnd=.08).model_dump(mode='json'))
    frames=s.load_frames(mid)
    assert [f.geometryAvailable for f in frames]==[True,True,False,False,False]
    assert all(not f.myTeam and not f.enemies for f in frames[2:])
    assert s.calibration_revision(mid).validInterval.end==.08
    s.promote_identity_for_match(mid,{'reviewed':True})
    assert s._stored_calibration_accepted(mid) is False
    assert s.derived_distance_for_match(mid)['availability']=='withheld'


def test_other_stream_calibration_and_unsupported_camera_are_refused(tmp_path):
    s=Storage(tmp_path/'store');mid=video(s,tmp_path)
    old=s.current_generation(mid).generationId
    p=profile().model_copy(update={'sourceStreamId':'other-camera'})
    with pytest.raises(Exception) as error:
        s.commit_calibration_for_match(mid,p.model_dump(mode='json'))
    assert getattr(error.value,'code',None)=='CALIBRATION_SOURCE_MISMATCH'
    assert s.current_generation(mid).generationId==old
    p=profile().model_copy(update={'cameraModel':'segmented'})
    with pytest.raises(Exception) as error:
        s.commit_calibration_for_match(mid,p.model_dump(mode='json'))
    assert getattr(error.value,'code',None)=='CAMERA_MODEL_UNSUPPORTED'
    assert s.current_generation(mid).generationId==old


def test_airborne_and_unknown_ground_ball_are_not_projected_as_measured(tmp_path):
    def prepare(rows):
        for i,row in enumerate(list(rows)):
            ball={**row,'Entity_Type':'ball','Track_ID':-1}
            if i==0: ball['airborne']=True
            if i==1: ball['groundPlane']=True
            rows.append(ball)
    s=Storage(tmp_path/'store');mid=video(s,tmp_path,prepare_rows=prepare)
    s.commit_calibration_for_match(mid,profile().model_dump(mode='json'))
    frames=s.load_frames(mid)
    assert frames[0].ball is None and frames[1].ball is not None and frames[2].ball is None
    assert 'AERIAL_NOT_GROUND_PLANE' in frames[0].coordinateProvenance['reasonCodes']
    assert frames[0].coordinateProvenance['sourceClock']=={'PTS':0,'TimeBaseNum':1,'TimeBaseDen':25}


@pytest.mark.parametrize('change,code',[
    ({'Source_Width':'not-a-number'},'SOURCE_OBSERVATIONS_REQUIRED'),
    ({'Source_X1':True},'SOURCE_OBSERVATIONS_REQUIRED'),
    ({'TimeBaseDen':0},'INVALID_SOURCE_CLOCK'),
    ({'PTS':999},'INVALID_SOURCE_CLOCK'),
])
def test_bad_source_metadata_refuses_without_publishing(tmp_path,change,code):
    s=Storage(tmp_path/'store');mid=video(s,tmp_path,prepare_rows=lambda rows:rows[0].update(change))
    before=s.current_generation(mid).generationId
    with pytest.raises(Exception) as error:
        s.commit_calibration_for_match(mid,profile().model_dump(mode='json'))
    assert getattr(error.value,'code',None)==code
    assert s.current_generation(mid).generationId==before
    assert s.calibration_revision(mid) is None


def test_source_dimensions_bound_to_calibration(tmp_path):
    s=Storage(tmp_path/'store');mid=video(s,tmp_path);before=s.current_generation(mid).generationId
    with pytest.raises(Exception) as error:
        s.commit_calibration_for_match(mid,profile(sourceWidth=999,sourceHeight=600).model_dump(mode='json'))
    assert getattr(error.value,'code',None)=='CALIBRATION_SOURCE_MISMATCH'
    assert s.current_generation(mid).generationId==before


def test_explicit_ground_flag_cannot_override_airborne_ball(tmp_path):
    def prepare(rows):
        rows.append({**rows[0],'Entity_Type':'ball','Track_ID':-1,'airborne':True,'groundPlane':True})
    s=Storage(tmp_path/'store');mid=video(s,tmp_path,prepare_rows=prepare)
    s.commit_calibration_for_match(mid,profile().model_dump(mode='json'))
    first=s.load_frames(mid)[0]
    assert first.ball is None
    assert 'AERIAL_NOT_GROUND_PLANE' in first.coordinateProvenance['reasonCodes']


def test_calibration_dimensions_and_candidate_config_commit_together(tmp_path):
    s=Storage(tmp_path/'store');mid=video(s,tmp_path)
    calibrated=profile().model_dump(mode='json')
    calibrated['pitchLengthM']=110.
    assert s.commit_calibration_for_match(mid,calibrated)['committed']
    assert s.get_match(mid).config.pitchLengthM==110.
    assert coords(s,mid)[0]==pytest.approx((12./110.*100.,30.))
    assert s.calibration_revision(mid).pitchLengthM==110.


@pytest.mark.parametrize('values',[
    {'manualHomographyPoints':[{'x':0.,'y':0.},{'x':1.,'y':0.},{'x':1.,'y':1.},{'x':0.,'y':1.}]},
    {'pitchLengthM':105.}, {'cameraProfile':'handheld_low_angle'},
])
def test_generic_config_cannot_relabel_a_new_camera_fit_as_accepted(tmp_path,values):
    from backend.app.review_service import ReviewService
    s=Storage(tmp_path/'store');mid=video(s,tmp_path)
    s.commit_calibration_for_match(mid,profile().model_dump(mode='json'))
    before=(s.current_generation(mid).generationId,s.list_corrections(mid))
    with pytest.raises(Exception) as error:
        ReviewService(s).configure(mid,values)
    assert getattr(error.value,'code',None)=='CALIBRATION_COMMIT_REQUIRED'
    assert (s.current_generation(mid).generationId,s.list_corrections(mid))==before


def test_calibration_translation_preserves_distances_scale_changes_them_and_undo_restores_source(tmp_path):
    from backend.app.review_service import ReviewService
    s = Storage(tmp_path / 'store')
    mid = video(s, tmp_path)
    raw = (s.generations.root(mid) / 'raw_rows.json').read_bytes()
    a = s.commit_calibration_for_match(mid, profile().model_dump(mode='json'))
    s.promote_identity_for_match(mid, {'reviewed': True})
    assert s.derived_distance_for_match(mid)['value'] == pytest.approx(4.)
    b = s.commit_calibration_for_match(mid, profile(dx=5.).model_dump(mode='json'))
    assert s.derived_distance_for_match(mid)['value'] == pytest.approx(4.)
    assert coords(s, mid)[0] == pytest.approx((17., 30.))
    c = s.commit_calibration_for_match(mid, profile(sx=.11).model_dump(mode='json'))
    assert s.derived_distance_for_match(mid)['value'] == pytest.approx(4.4)
    ReviewService(s).configure(mid, {'attackDirection': 'right_to_left'})
    s.undo_correction(mid, c['correction']['correctionId'])
    assert coords(s, mid)[0] == pytest.approx((17., 30.))
    s.undo_correction(mid, b['correction']['correctionId'])
    assert coords(s, mid)[0] == pytest.approx((12., 30.))
    s.undo_correction(mid, a['correction']['correctionId'])
    assert coords(s, mid)[0] == pytest.approx((9., 9.))
    assert s.calibration_revision(mid) is None
    assert s.get_match(mid).config.attackDirection == 'right_to_left'
    assert s.derived_distance_for_match(mid)['availability'] == 'withheld'
    assert (s.generations.root(mid) / 'raw_rows.json').read_bytes() == raw
