"""C05 evaluator acceptance extensions; tiny synthetic inputs, real pinned scorer.

No detector/training call. The dummy checkpoint is a byte-identity fixture, not a
model; scores concern these declared predictions, never checkpoint accuracy.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil

import pytest

pytestmark = pytest.mark.integration


def fixture(root, *, prediction=True, namespace='synthetic'):
    root.mkdir(parents=True,exist_ok=True)
    def save(name,payload):
        data=payload if isinstance(payload,bytes) else json.dumps(payload).encode()
        (root/name).write_bytes(data)
        return dict(path=name,sha256=hashlib.sha256(data).hexdigest(),byteSize=len(data))
    source=save('source.bin',b'synthetic-source')
    weights=save('weights.pt',b'synthetic-checkpoint-not-a-model')
    protocol=save('protocol.json',{'version':3,'evaluationFrames':{'targetFps':5}})
    split=save('split.json',{'schemaVersion':1,'trainingSources':[],'validationSources':[]})
    task=dict(taskId='t1',sourceStartFrame=0,sourceEndFrameExclusive=10,sourceFps=25,
        evaluationFrameStep=5,evaluationFrameCount=2,sourceWidth=100,sourceHeight=100,
        videoSha256=source['sha256'])
    labels={'schemaVersion':'football_analysis_pilot_labels_v3','taskId':'t1',
        'sourceVideoSha256':source['sha256'],'independentAnnotation':True,'pipelineOutputUsed':False,
        'annotatorId':'synthetic-fixture','lockedAt':'2026-01-01T00:00:00Z','pitchReference':None,
        'events':[], 'frames':[{'frameId':i,'ball':{'visibility':'not_visible','bbox':None,'pitchPositionMeters':None},
            'entities':[{'trackId':'p1','kind':'player','team':'home','bbox':[10,10,20,20],'pitchPositionMeters':None}],
            'possession':{'state':'unknown','team':'unknown','trackId':None}} for i in (0,5)]}
    predictions=[dict(Frame_ID=i,Entity_Type='player',Track_ID=1,Source_X1=10,Source_Y1=10,Source_X2=20,Source_Y2=20) for i in (0,5)] if prediction else []
    pd=save('predictions.json',predictions)
    provenance=save('prediction-provenance.json',dict(schemaVersion=1,kind='native_image_space_predictions',
        taskId='t1',sourceSha256=source['sha256'],predictionSha256=pd['sha256'],
        checkpointSha256=weights['sha256'],coordinates='source_pixels',namespace=namespace,handEdited=False))
    manifest={'schemaVersion':2,'scope':'image_space_tracking','namespace':namespace,
        'scorerCommit':'12c8791b303e0a0b50f753af204249e622d0281a',
        'protocol':protocol,'checkpoint':weights,'trainingSplit':split,
        'tasks':[{'task':task,'stratum':'wide','source':source,'labels':save('labels.json',labels),
            'predictions':pd,'predictionProvenance':provenance}]}
    path=root/'manifest.json';path.write_text(json.dumps(manifest))
    return path,manifest,save


def policy(manifest):
    return dict(policyId='synthetic-test-only',scope='image_space_tracking',namespace=manifest['namespace'],
        protocolSha256=manifest['protocol']['sha256'],checkpointSha256=manifest['checkpoint']['sha256'],
        requiredTaskIds=['t1'],requiredStrata=['wide'],minimumMinutes=0,minimumFramesPerTask=2,
        metrics={'HOTA':{'minimum':.5,'units':'fraction'},'IDF1':{'minimum':.5,'units':'fraction'}})


@pytest.fixture
def scorer_root():
    value=os.environ.get('C05_TRACKEVAL_ROOT')
    if not value:pytest.skip('C05 dedicated lane supplies the pinned real TrackEval source')
    return Path(value)


def test_v3t39_verified_inventory_is_not_scorer_execution(tmp_path):
    from backend.app.workbench.evaluation import current_repository_evaluation_gate
    path,manifest,_=fixture(tmp_path/'case')
    manifest['results']={'HOTA':1,'IDF1':1};path.write_text(json.dumps(manifest))
    gate=current_repository_evaluation_gate(manifest_path=path)
    assert not gate.accepted and gate.executionStatus=='not_run'
    assert gate.scoreStatus=='unavailable'


@pytest.mark.parametrize('prediction,expected',[(True,1.0),(False,0.0)])
def test_v3t40_real_scorer_preserves_zero_and_separates_acceptance(tmp_path,scorer_root,prediction,expected):
    from backend.app.evaluation_verifier import verify_evaluation_manifest
    path,manifest,_=fixture(tmp_path/'case',prediction=prediction)
    gate=verify_evaluation_manifest(path,trackeval_root=scorer_root)
    assert gate.inventoryStatus=='verified' and gate.executionStatus=='completed',gate
    assert gate.scoreStatus=='valid' and gate.scores['t1']['HOTA']==pytest.approx(expected)
    assert not gate.accepted and gate.acceptanceStatus=='not_evaluated'
    assert 'ACCEPTANCE_POLICY_MISSING' in gate.reasonCodes
    result=verify_evaluation_manifest(path,trackeval_root=scorer_root,acceptance_policy=policy(manifest))
    assert result.accepted is prediction
    assert result.acceptanceStatus==('passed' if prediction else 'failed')
    assert result.executionEvidence['checkpointSha256']==manifest['checkpoint']['sha256']
    assert result.executionEvidence['units']=='fraction'
    assert result.executionEvidence['modelInferenceExecuted'] is False


@pytest.mark.parametrize('artifact',['labels.json','predictions.json','weights.pt','source.bin','protocol.json'])
def test_v3t39_changed_or_missing_artifact_blocks_execution(tmp_path,artifact):
    from backend.app.evaluation_verifier import verify_evaluation_manifest
    path,_,_=fixture(tmp_path/'case');(path.parent/artifact).write_bytes(b'changed')
    gate=verify_evaluation_manifest(path,trackeval_root=tmp_path/'must-not-execute')
    assert gate.inventoryStatus=='incomplete' and gate.executionStatus=='not_run'
    assert not gate.accepted
    (path.parent/artifact).unlink()
    assert not verify_evaluation_manifest(path,trackeval_root=tmp_path/'must-not-execute').accepted


def test_v3t39_wrong_scope_and_symlink_refused(tmp_path):
    from backend.app.evaluation_verifier import verify_evaluation_manifest
    path,m,_=fixture(tmp_path/'case')
    labels=path.parent/'labels.json'; outside=tmp_path/'foreign.json';labels.rename(outside);labels.symlink_to(outside)
    gate=verify_evaluation_manifest(path,trackeval_root=tmp_path/'unused')
    assert gate.inventoryStatus=='incomplete' and gate.executionStatus=='not_run'


@pytest.mark.parametrize('change', ['units','stratum','checkpoint','coverage'])
def test_v3t41_policy_requires_all_scope_units_and_coverage(tmp_path,scorer_root,change):
    from backend.app.evaluation_verifier import verify_evaluation_manifest
    path,m,_=fixture(tmp_path/'case');p=policy(m)
    if change=='units':p['metrics']['HOTA']['units']='guess'
    if change=='stratum':p['requiredStrata'].append('closeup')
    if change=='checkpoint':p['checkpointSha256']='f'*64
    if change=='coverage':p['minimumFramesPerTask']=3
    gate=verify_evaluation_manifest(path,trackeval_root=scorer_root,acceptance_policy=p)
    assert gate.scoreStatus=='valid' and not gate.accepted
    assert gate.acceptanceStatus in ('failed','not_evaluated')


@pytest.mark.parametrize('fault',['pseudo_labels','split_overlap','foreign_checkpoint'])
def test_v3t42_provenance_cannot_borrow_labels_or_checkpoint(tmp_path,fault):
    from backend.app.evaluation_verifier import verify_evaluation_manifest
    path,m,save=fixture(tmp_path/'case',namespace='held_out')
    if fault=='pseudo_labels':
        labels=json.loads((path.parent/'labels.json').read_text());labels['pipelineOutputUsed']=True
        m['tasks'][0]['labels']=save('labels.json',labels)
    elif fault=='split_overlap':
        m['trainingSplit']=save('split.json',{'schemaVersion':1,'trainingSources':[m['tasks'][0]['source']],'validationSources':[]})
    else:
        provenance=json.loads((path.parent/'prediction-provenance.json').read_text());provenance['checkpointSha256']='f'*64
        m['tasks'][0]['predictionProvenance']=save('prediction-provenance.json',provenance)
    path.write_text(json.dumps(m))
    gate=verify_evaluation_manifest(path,trackeval_root=tmp_path/'unused',acceptance_policy=policy(m))
    assert gate.inventoryStatus=='incomplete' and gate.executionStatus=='not_run' and not gate.accepted


def test_v3t42_csv_epoch_is_not_checkpoint_binding(tmp_path):
    from backend.app.training_quality_gate import _validation_metric_summary
    path=tmp_path/'results.csv';path.write_text('epoch,metrics/mAP50(B),fitness\n1,0.9,0.9\n2,0.3,0.3\n')
    result=_validation_metric_summary(path,best_epoch=1)
    assert result.get('checkpointMatched') is False
    assert result['diagnosticEpochMatched'] is True
    assert result['checkpointBindingStatus']=='unverified'
