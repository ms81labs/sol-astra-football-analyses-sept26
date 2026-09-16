"""Behavioral checks for the released detector and changing camera calibration."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import backend.run_guerilla as pipeline
from backend.app import gpu_worker, proof_runtime, video_pipeline
from backend.app.homography_utils import build_homography_from_points, point_to_pitch
from backend.app.runtime_options import ProofRuntimeOptions
from backend.app.schemas import MatchConfig
from backend.pitch_detector import compute_pitch_homography

PROFILE = 'ball_probe_only_v7_3_crop_256'
MANIFEST = Path(__file__).resolve().parents[1] / 'release/v7.3.json'


class Capture:
    def __init__(self, frames):
        self.frames = iter(frames)
    def isOpened(self): return True
    def get(self, _): return 5
    def read(self):
        frame = next(self.frames, None)
        return frame is not None, frame
    def set(self, *_): pass
    def release(self): pass


def box(cls, x, y):
    return SimpleNamespace(cls=[cls], conf=[0.9], id=[1], xyxy=np.array([[x-2, y-2, x+2, y+2]]))


def test_current_manifest_detector_matches_crop_training():
    profile = json.loads(MANIFEST.read_text())['runtimeOptions']['auxiliary_ball_model_profile']
    assert pipeline.detector_ball_class_ids(profile) == [0]
    assert pipeline.detector_player_class_ids(profile) == []
    assert pipeline.detector_probe_recovery_settings(profile) == {'recoveryConf': .1, 'recoveryImgsz': 256}
    with pytest.raises(ValueError, match='detector profile'):
        pipeline.detector_profile_spec('typo')


def test_auto_and_manual_calibration_have_same_canonical_coordinates():
    corners = [[0,0],[200,0],[200,100],[0,100]]
    auto = compute_pitch_homography(corners)
    manual = build_homography_from_points(corners)
    for point in [(100,50), (200,100), (0,0)]:
        assert point_to_pitch(auto,*point) == pytest.approx(point_to_pitch(manual,*point))


def test_released_crop_detector_preserves_padding_offsets_and_input_size(monkeypatch):
    frame = np.full((500,600,3), 123, dtype=np.uint8)
    monkeypatch.setattr(pipeline.cv2, 'VideoCapture', lambda _: Capture([frame]))
    calls = []
    class Model:
        def predict(self, image, **kwargs):
            calls.append((image.copy(), kwargs))
            # All four centered crops must place the physical ball at (10,20).
            return [SimpleNamespace(boxes=[box(0,image.shape[1]/2,image.shape[0]/2)])]
    rows = pipeline.recover_ball_rows('fake',model=Model(), H=np.eye(3), pitch_points=None,
        fps=5,frame_interval=1,detector_profile=PROFILE,recovery_imgsz=1600,recovery_conf=.001,
        crop_windows_by_frame={0:[{'window':(0,0,400,400),'proposalSeedCenter':(10,20),
            'proposalWindowKind':'direct_seed_tight'}]})
    assert {image.shape[:2] for image,_ in calls} == {(s,s) for s in (128,192,256,384)}
    assert all(kw['imgsz']==256 and kw['conf']==.1 and kw['classes']==[0] for _,kw in calls)
    assert all(np.all(image[0,0]==0) for image,_ in calls)
    assert all(np.all(image[image.shape[0]//2,image.shape[1]//2]==123) for image,_ in calls)
    assert rows and {(row['X'],row['Y']) for row in rows} == {(10.,20.)}


def test_crop_detector_does_not_shrink_a_whole_frame_when_proposals_are_missing(monkeypatch):
    monkeypatch.setattr(pipeline.cv2,'VideoCapture',lambda _:Capture([np.zeros((720,1280,3),np.uint8)]))
    class Model:
        def predict(self,*a,**kw): pytest.fail('crop model must receive a supported local proposal')
    assert pipeline.recover_ball_rows('fake',model=Model(),H=np.eye(3),pitch_points=None,
        fps=5,frame_interval=1,detector_profile=PROFILE,crop_windows_by_frame={}) == []


def test_recovery_projects_each_camera_segment_with_its_own_calibration(monkeypatch):
    frames=[np.zeros((200,300,3),np.uint8) for _ in range(2)]
    monkeypatch.setattr(pipeline.cv2,'VideoCapture',lambda _:Capture(frames))
    initial=[[0,0],[100,0],[100,100],[0,100]]
    shifted=[[100,0],[200,0],[200,100],[100,100]]
    class Model:
        index=0
        def predict(self,*a,**kw):
            x=50+100*self.index
            self.index+=1
            return [SimpleNamespace(boxes=[box(32,x,50)])]
    rows=pipeline.recover_ball_rows('fake',model=Model(),H=np.eye(3),pitch_points=initial,
        fps=5,frame_interval=1,calibrations=[(0,np.eye(3),initial),(1,np.array([[1.,0,-100],[0,1,0],[0,0,1]]),shifted)])
    assert [(r['Frame_ID'],r['X'],r['Y']) for r in rows] == [(0,50.,50.),(1,50.,50.)]


def test_tracking_updates_polygon_and_forwards_calibration_history_to_both_passes(monkeypatch):
    frame=np.zeros((200,300,3),np.uint8)
    initial=[[0,0],[100,0],[100,100],[0,100]]
    shifted=[[100,0],[200,0],[200,100],[100,100]]
    class Model:
        def track(self,**kw):
            return iter([SimpleNamespace(orig_img=frame,boxes=[box(32,x,50),box(0,x,48)]) for x in (50,150)])
        def predict(self,*a,**kw): return []
    monkeypatch.setattr(pipeline,'YOLO',lambda _:Model())
    monkeypatch.setattr(pipeline.cv2,'VideoCapture',lambda _:Capture([frame]))
    monkeypatch.setattr(pipeline,'resolve_homography',lambda *a,**kw:(np.eye(3),initial))
    monkeypatch.setattr(pipeline,'HOMOGRAPHY_RECALC_FRAMES',1)
    monkeypatch.setattr(pipeline,'AUTO_HOMOGRAPHY_AVAILABLE',True)
    monkeypatch.setattr(pipeline,'detect_pitch_corners',lambda _:shifted)
    monkeypatch.setattr(pipeline,'compute_pitch_homography',lambda _:np.array([[1.,0,-100],[0,1,0],[0,0,1]]))
    monkeypatch.setattr(pipeline,'extract_torso_color',lambda *a:None)
    calls=[]
    monkeypatch.setattr(pipeline,'recover_ball_rows',lambda *a,**kw:calls.append(kw) or [])
    monkeypatch.setattr(pipeline,'run_ball_recovery_experiment',lambda *a,**kw:calls.append(kw) or [])
    monkeypatch.setattr(pipeline,'ball_rows_need_recovery',lambda _:True)
    result=pipeline.process_video('fake',return_rows=True)
    primary=next(s for s in result['ballPipelineTrace']['stages'] if s['stage']=='processVideoPrimary')
    assert primary['ballFrameCount']==2
    assert len(calls)==2
    for call in calls:
        assert [entry[0] for entry in call['calibrations']]==[0,1]
        assert call['calibrations'][0][2]==initial
        assert call['calibrations'][1][2]==shifted


def test_acquisition_contract_reaches_local_remote_and_video_execution(monkeypatch,tmp_path):
    options=ProofRuntimeOptions.from_mapping(json.loads(MANIFEST.read_text())['runtimeOptions'])
    paths={entry['id']: tmp_path/entry['id'] for entry in json.loads(MANIFEST.read_text())['artifacts']}
    monkeypatch.setattr(proof_runtime,'materialize_artifact_reference',lambda ref,*a,**kw:paths[ref.artifact_id])
    kwargs=proof_runtime.materialize_proof_runtime_options(options,storage_root=tmp_path,environment='local',manifest_path=MANIFEST)
    assert kwargs['primary_acquisition_mode']==options.primary_acquisition_mode
    assert gpu_worker._materialize_local_options(options,paths)['primary_acquisition_mode']==options.primary_acquisition_mode
    calls=[]
    monkeypatch.setattr(video_pipeline,'_process_video_impl',lambda *a,**kw:calls.append(kw) or {'rows':[{}]})
    video_pipeline.process_video_input(Path('fake'),MatchConfig(autoHomography=True),**kwargs)
    assert calls[0]['primary_acquisition_mode']==options.primary_acquisition_mode
    with pytest.raises(ValueError,match='acquisition'):
        gpu_worker._materialize_local_options(replace(options,primary_acquisition_mode='unimplemented'),paths)
    with pytest.raises(ValueError,match='acquisition'):
        pipeline.process_video('fake',primary_acquisition_mode='unimplemented')


def test_current_release_executes_crop_proposals_in_probe_and_recovery(monkeypatch):
    frame=np.full((480,640,3),123,dtype=np.uint8)
    calls=[]
    class Primary:
        def track(self,**kw):
            return iter([SimpleNamespace(orig_img=frame,boxes=[box(0,300,200)])])
    class Auxiliary:
        def predict(self,image,**kwargs):
            calls.append((image.shape,kwargs))
            # A miss exercises retry handling too: it must stay at the trained input size.
            return [SimpleNamespace(boxes=[])]
    monkeypatch.setattr(pipeline,'YOLO',lambda path:Auxiliary() if path=='aux' else Primary())
    monkeypatch.setattr(pipeline.cv2,'VideoCapture',lambda _:Capture([frame]))
    monkeypatch.setattr(pipeline,'extract_torso_color',lambda *a:None)
    result=pipeline.process_video('fake',primary_model_path='primary',auxiliary_ball_model_path='aux',
        auxiliary_ball_model_profile=PROFILE,homography_points=[[0,0],[640,0],[640,480],[0,480]],
        auto_homography=False,return_rows=True)
    assert calls
    assert {shape[:2] for shape,_ in calls}=={(s,s) for s in (128,192,256,384)}
    assert all(kw['imgsz']==256 and kw['conf']==.1 and kw['classes']==[0] for _,kw in calls)
    trace=result['ballPipelineTrace']
    assert trace['probeDetectorProfile']==trace['recoveryDetectorProfile']==PROFILE
    assert trace['primaryAcquisitionMode']=='anchored_player_ranked_context_960'
    assert result['recoveryDebug']['recoveryAttempted'] is True


def test_experiment_forwards_calibration_history_to_every_recovery_profile(monkeypatch):
    frame=np.zeros((200,300,3),np.uint8)
    monkeypatch.setattr(pipeline.cv2,'VideoCapture',lambda _:Capture([frame]))
    calls=[]
    monkeypatch.setattr(pipeline,'recover_ball_rows',lambda *a,**kw:calls.append(kw) or [])
    calibrations=[(0,np.eye(3),None),(1,np.array([[1.,0,-100],[0,1,0],[0,0,1]]),None)]
    profiles=[{'name':f'profile-{i}','settings':{'imgsz':1280+i*320,'conf':.1}} for i in range(2)]
    pipeline.run_ball_recovery_experiment('fake',model=object(),H=np.eye(3),pitch_points=None,
        fps=5,frame_interval=1,imgsz=1280,conf=.1,profiles=profiles,calibrations=calibrations)
    assert len(calls)==2
    assert all(call['calibrations'] is calibrations for call in calls)


@pytest.mark.parametrize('anchor', [(200,200), (850,330)])
def test_real_ranked_and_context_proposals_keep_distinct_crop_locations(anchor):
    rows=[pipeline.build_tracking_row(frame_id=0,timestamp=0,entity_type='player',track_id=i,
        pitch_x=50,pitch_y=50,detection_conf=.9,source_box=source_box)
        for i,source_box in enumerate([(850,300,890,400),(1350,350,1390,450)])]
    windows,_=pipeline._build_player_proposal_crop_windows_by_frame((1080,1920,3),
        frame_interval=1,frame_count=1,player_rows=rows,observed_source_anchors={0:anchor})
    proposals=windows[0]
    assert len({pipeline._window_center(spec['window']) for spec in proposals})>1
    converted=pipeline._v7_3_crop_windows(proposals)
    for spec in proposals:
        expected=anchor if spec['proposalWindowKind']=='direct_seed_tight' else pipeline._window_center(spec['window'])
        matching=[crop for crop in converted if crop['proposalWindowKind']==spec['proposalWindowKind']]
        assert any(pipeline._window_center(crop['window'])==expected for crop in matching)
        assert all(crop['proposalSeedCenter']==anchor for crop in matching)


def test_unseeded_proposals_are_bounded_and_rotate_across_individual_players():
    rows=[pipeline.build_tracking_row(frame_id=frame_id,timestamp=frame_id/5,entity_type='player',
        track_id=track_id,pitch_x=50,pitch_y=50,detection_conf=.9,
        source_box=(300+300*track_id,400,340+300*track_id,510))
        for frame_id in range(2) for track_id in range(5)]
    windows,diagnostics=pipeline._build_player_proposal_crop_windows_by_frame((1080,1920,3),
        frame_interval=1,frame_count=2,player_rows=rows,observed_source_anchors={})
    assert set(windows)=={0,1}
    assert all(len(specs)<=3 for specs in windows.values())
    assert {pipeline._window_center(spec['window']) for specs in windows.values() for spec in specs} == {
        (320.+300*track_id,455.) for track_id in range(5)}
    assert all(spec['proposalSeedMode']=='none' and 'proposalSeedCenter' not in spec
        for specs in windows.values() for spec in specs)
    assert diagnostics['proposalFramesWithoutAnchorSeed']==2
    assert diagnostics['proposalFramesWithAnchorSeed']==0


def test_probe_and_recovery_see_ball_near_noncentral_player_without_primary_ball(monkeypatch):
    frame=np.zeros((1080,1920,3),np.uint8)
    frame[490:510,390:410]=255
    class Primary:
        def track(self,**kw):
            boxes=[SimpleNamespace(cls=[0],conf=[.9],id=[x],xyxy=np.array([[x-20,400,x+20,510]]))
                for x in (400,1500)]
            return iter([SimpleNamespace(orig_img=frame,boxes=boxes)])
    predictions=[]
    stage={'value':None}
    class Auxiliary:
        def predict(self,image,**kwargs):
            marker=np.argwhere(image[:,:,0]==255)
            predictions.append((stage['value'],bool(len(marker))))
            boxes=[]
            if len(marker):
                y1,x1=marker.min(axis=0)
                y2,x2=marker.max(axis=0)+1
                boxes=[SimpleNamespace(cls=[0],conf=[.9],id=None,xyxy=np.array([[x1,y1,x2,y2]]))]
            return [SimpleNamespace(boxes=boxes)]
    monkeypatch.setattr(pipeline,'YOLO',lambda path:Auxiliary() if path=='aux' else Primary())
    monkeypatch.setattr(pipeline.cv2,'VideoCapture',lambda _:Capture([frame]))
    monkeypatch.setattr(pipeline,'extract_torso_color',lambda *a:None)
    observed=[]
    real_recover=pipeline.recover_ball_rows
    def recover(*args,**kwargs):
        result=real_recover(*args,**kwargs)
        rows=result[0] if isinstance(result,tuple) else result
        observed.append((stage['value'],rows))
        return result
    monkeypatch.setattr(pipeline,'recover_ball_rows',recover)
    pipeline.process_video('fake',primary_model_path='primary',auxiliary_ball_model_path='aux',
        auxiliary_ball_model_profile=PROFILE,homography_points=[[0,0],[1920,0],[1920,1080],[0,1080]],
        auto_homography=False,return_rows=True,
        progress_callback=lambda event:stage.update(value=event['workerStage']))
    for expected_stage in ('probeObservedPass','recoverySelection'):
        assert any(actual_stage==expected_stage and has_marker for actual_stage,has_marker in predictions)
        rows=[row for actual_stage,batch in observed if actual_stage==expected_stage for row in batch]
        assert rows
        assert any((row['Source_X1'],row['Source_Y1'],row['Source_X2'],row['Source_Y2'])==(390.,490.,410.,510.) for row in rows)
    probe_rows=next(rows for actual_stage,rows in observed if actual_stage=='probeObservedPass')
    assert all(row['ProposalSeedMode']=='none' for row in probe_rows)
    assert all(not pipeline._proposal_row_is_anchored(row) for row in probe_rows)
