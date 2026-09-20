"""C05 same-match reuse with actual stores/processes; no perception/model calls."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from backend.app.processor import process_match
from backend.app.schemas import MatchConfig
from backend.app.storage import Storage
from backend.tests.test_audit_v2_h05_recompute import _install_video_match, TRACKING_FIXTURE

pytestmark = pytest.mark.integration


def install(tmp_path,mode):
    s=Storage(tmp_path/'store')
    if mode=='video':mid=_install_video_match(s,tmp_path)
    else:
        source=tmp_path/'tracking.json';source.write_bytes(TRACKING_FIXTURE.read_bytes())
        mid=s.create_match('Tracking','tracking_json',source.name,source,MatchConfig()).id
        process_match(s,s.create_job(mid).id)
    return s,mid


WORKER='''
import sys,json
import backend.tests.conftest
from backend.app.storage import Storage
from backend.app.review_service import ReviewService
import backend.app.processor as processor
processor.process_video_input=lambda *a,**k: (_ for _ in ()).throw(AssertionError('unexpected detector'))
s=Storage(sys.argv[1]);mid=sys.argv[2]
if sys.argv[3]=='rebuild':
 print(json.dumps(s.execute_recompute(mid,'team_mapping').model_dump(mode='json')))
else:
 ReviewService(s).configure(mid,{'attackDirection':'right_to_left'})
 print(json.dumps({'generation':s.current_generation(mid).generationId}))
'''


def child(storage,mid,action='rebuild',fault=False):
    env={**os.environ,'GA_TEST_FAULTS':'1' if fault else '0','GA_TEST_FAULT_POINT':'during_generation_write' if fault else ''}
    return subprocess.run([sys.executable,'-c',WORKER,str(storage.storage_root),mid,action],
        cwd=Path(__file__).parents[2],env=env,capture_output=True,text=True,timeout=60)


@pytest.mark.parametrize('mode',['video','tracking'])
def test_v3t37_real_artifact_hit_reopen_and_source_miss(tmp_path,mode):
    s,mid=install(tmp_path,mode);first=s.current_generation(mid)
    result=child(s,mid)
    assert result.returncode==0,result.stderr
    receipt=json.loads(result.stdout)
    assert receipt['kind']=='executed' and receipt['detectorCalls']==0
    assert receipt['outputGeneration']!=first.generationId
    current=s.current_generation(mid)
    source=s.get_match_input_path(mid);source.write_bytes(b'changed source')
    result=child(s,mid)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['kind']=='refused'
    assert s.current_generation(mid)==current


@pytest.mark.parametrize('mode',['video','tracking'])
def test_v3t50_pinned_reader_survives_killed_writer_then_verified_reuse(tmp_path,mode):
    s,mid=install(tmp_path,mode)
    with s.generation_snapshot(mid) as old:
        old_bytes=(s._match_dir(mid)/'generations'/old.generationId/'frames.json').read_bytes()
        failed=child(s,mid,'configure',fault=True)
        assert failed.returncode!=0
        assert s.current_generation(mid).generationId==old.generationId
        result=child(s,mid,'configure')
        assert result.returncode==0,result.stderr
        assert json.loads(result.stdout)['generation']!=old.generationId
        assert (s._match_dir(mid)/'generations'/old.generationId/'frames.json').read_bytes()==old_bytes
    before=s.current_generation(mid).generationId
    raw=s._match_dir(mid)/'raw_rows.json' if mode=='video' else s.get_match_input_path(mid)
    original=raw.read_bytes();raw.write_bytes(b'{broken')
    result=child(s,mid)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['kind']=='refused'
    assert s.current_generation(mid).generationId==before
    raw.write_bytes(original)
    result=child(s,mid)
    assert result.returncode==0 and json.loads(result.stdout)['kind']=='executed'


def test_v3t36_semantic_change_keeps_observations_but_changes_review_identity(tmp_path):
    from backend.app.review_service import ReviewService
    s,mid=install(tmp_path,'tracking')
    before=s.generations.manifest(mid,s.current_generation(mid).generationId)[0]
    ReviewService(s).configure(mid,{'attackDirection':'right_to_left'})
    after=s.generations.manifest(mid,s.current_generation(mid).generationId)[0]
    assert before.observationIdentity==after.observationIdentity and before.observationIdentity
    assert before.projectionIdentity==after.projectionIdentity
    assert before.reviewedIdentity!=after.reviewedIdentity and after.reviewedIdentity
    assert before.reportIdentity!=after.reportIdentity
    assert after.observationInputs['reuseScope']=='same_match_post_perception'


def test_v3t37_bytes_swapped_during_materialization_never_publish(tmp_path,monkeypatch):
    from backend.app.review_service import ReviewService
    s,mid=install(tmp_path,'video');before=s.current_generation(mid).generationId
    method=ReviewService._materialize_inputs
    def changed(self,*args,**kwargs):
        result=method(self,*args,**kwargs)
        (s._match_dir(mid)/'raw_rows.json').write_text('[]')
        return result
    monkeypatch.setattr(ReviewService,'_materialize_inputs',changed)
    result=s.execute_recompute(mid,'team_mapping')
    assert result.kind=='refused' and s.current_generation(mid).generationId==before
