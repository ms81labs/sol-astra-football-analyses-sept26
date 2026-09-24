"""C05 behavioural counterexamples and positive controls; no model/network calls."""
import json

import pytest

from backend.app.domain_types import Interval
from backend.app.workbench.cache import DetectionIdentity
from backend.app.workbench.evaluation import current_repository_evaluation_gate, evaluate_protocol_prerequisites, score_hota_idf1

pytestmark = pytest.mark.integration


def detection(**changes):
    values = dict(source_sha256='a'*64, stream_index=0, interval=Interval(start=0, end=1),
        weights_sha256='b'*64, preprocessing_id='test-preprocessing', class_map_id='test-class-map',
        precision='fp32', runtime_build='test-runtime')
    return DetectionIdentity(**{**values, **changes})


def legacy_manifest(path):
    path.write_text(json.dumps(dict(schemaVersion=1,completeTasks=18,completeMinutes=30,
        lockedLabelsPresent=True,nativePredictionsPresent=True,teamDeclarationsPresent=True,
        scorerReplayable=True,artifacts=[{'kind':'labels','sha256':'a'*64},
            {'kind':'predictions','sha256':'b'*64}],scorerVersion='trackeval@12c8791',
        sourceIdentity='match',results={'hota':.9,'idf1':.9})))
    return path


@pytest.mark.parametrize('changes', [dict(source_sha256=None),dict(source_sha256='0'*64),
    dict(runtime_build='unspecified'),dict(preprocessing_id=float('nan'))])
def test_v3t38_unknown_identity_is_stable_null_not_a_cache_key(changes):
    assert detection(**changes).digest() is None
    assert not detection(**changes).reusable


def test_v3t36_known_identity_positive_control():
    assert detection().digest() == detection().digest()
    assert detection().reusable
    assert detection(weights_sha256='c'*64).digest() != detection().digest()


def test_v3t39_manifest_metadata_cannot_prove_scorer_execution_or_acceptance(tmp_path):
    gate=current_repository_evaluation_gate(manifest_path=legacy_manifest(tmp_path/'manifest.json'))
    assert gate.accepted is False
    assert gate.status != 'scored'


def test_v3t40_prerequisites_are_not_accuracy_acceptance():
    gate=evaluate_protocol_prerequisites(complete_tasks=18,complete_minutes=30,
        locked_labels_present=True,native_predictions_present=True,
        team_declarations_present=True,scorer_replayable=True)
    assert not gate.accepted
    assert gate.status == 'prerequisites_ok'


@pytest.mark.parametrize('scores', [(2,2),(-.1,.5),(.9,.9)])
def test_v3t40_undeclared_units_never_become_valid_scores(scores):
    result=score_hota_idf1(label_space='image_space',hand_edited_summary=False,
        native_predictions_present=True,scorer_executed=True,hota=scores[0],idf1=scores[1],
        prediction_digest='a'*64,label_digest='b'*64,scorer_version='trackeval@12c8791',source_identity='m')
    assert not result['scored']


def test_v3t37_identity_equality_without_an_artifact_does_not_skip_perception():
    from backend.app.video_pipeline import reprocess_for_change
    calls=[]
    result=reprocess_for_change(change='perception',previous_identity='a'*64,current_identity='a'*64,
        vision=lambda: calls.append(1) or {'rows':[{'Frame_ID':0}]})
    assert calls == [1]
    assert not result['reused']


def test_v3t37_modified_observations_are_refused_without_publishing(tmp_path):
    from backend.tests.test_audit_v2_h05_recompute import _install_video_match
    from backend.app.storage import Storage
    storage=Storage(tmp_path/'store');mid=_install_video_match(storage,tmp_path)
    before=storage.current_generation(mid).generationId
    path=storage._match_dir(mid)/'raw_rows.json'
    rows=json.loads(path.read_text());rows[0]['Conf']=.12345;path.write_text(json.dumps(rows))
    result=storage.execute_recompute(mid,'team_mapping').model_dump(mode='json')
    assert result['kind'] == 'refused'
    assert storage.current_generation(mid).generationId == before


def test_v3t37_artifact_get_verifies_bytes_and_scope(tmp_path):
    from backend.app.workbench.artifacts import ArtifactStore
    store=ArtifactStore(tmp_path/'artifacts')
    key=store.put(b'original',namespace='development')
    assert store.get(key,namespace='development')==b'original'
    with pytest.raises((KeyError,ValueError)): store.get(key,namespace='evaluation')
    (store.root/'development'/key).write_bytes(b'corrupt')
    with pytest.raises((KeyError,ValueError)): store.get(key,namespace='development')


def test_v3t36_effective_files_invalidate_only_affected_layers(tmp_path,monkeypatch):
    monkeypatch.setattr("backend.app.perception_identity._detector_defaults",lambda: "synthetic-defaults")
    from backend.app.perception_identity import capture_inputs, layered_identities
    source=tmp_path/'clip.mp4';source.write_bytes(b'video')
    primary=tmp_path/'main.pt';primary.write_bytes(b'weights')
    auxiliary=tmp_path/'ball.pt';auxiliary.write_bytes(b'ball weights')
    tracker=tmp_path/'botsort.yaml';tracker.write_text('tracker_type: botsort\ntrack_high_thresh: 0.5\n')
    seed=tmp_path/'seed.json';seed.write_text('{"selected":1}')
    def snapshot():
        return capture_inputs(source,model_path=str(primary),tracker_path=tracker,
            auxiliary_ball_model_path=str(auxiliary),seed_paths={'reviewed':str(seed)},
            acquisition_mode='anchored_player_ranked_context_960',repair_profile=None,
            auxiliary_profile='coco_tracking_full',geometry={'auto':True})
    clock={'sourceSha256':__import__('hashlib').sha256(b'video').hexdigest(),
           'timeBaseNum':1,'timeBaseDen':25,'rotation':0,'frameCount':50,'nominalFps':25}
    payload={'precision':'fp32','decodeAnchors':{'beginning':0,'end':2}}
    def layers(inputs):return layered_identities(inputs,inputs,payload,clock,runtime_build='synthetic-build')
    first=layers(snapshot())
    assert first['observationIdentity']['reusable']
    tracker.write_text('# harmless whitespace\ntrack_high_thresh: .5\ntracker_type: botsort\n')
    assert layers(snapshot())==first
    tracker.write_text('tracker_type: botsort\ntrack_high_thresh: 0.6\n')
    second=layers(snapshot())
    assert second['detectionIdentity']==first['detectionIdentity']
    assert second['trackingIdentity']['digest']!=first['trackingIdentity']['digest']
    auxiliary.write_bytes(b'new ball weights');third=layers(snapshot())
    assert third['trackingIdentity']==second['trackingIdentity']
    assert third['observationIdentity']['digest']!=second['observationIdentity']['digest']
    seed.write_text('{"selected":2}');fourth=layers(snapshot())
    assert fourth['trackingIdentity']==third['trackingIdentity']
    assert fourth['observationIdentity']['digest']!=third['observationIdentity']['digest']
    before=snapshot();primary.write_bytes(b'changed during run')
    unstable=layered_identities(before,snapshot(),payload,clock,runtime_build='synthetic-build')
    assert unstable['detectionIdentity']['digest'] is None
    assert 'INPUT_CHANGED_DURING_EXECUTION' in unstable['detectionIdentity']['reasonCodes']


def test_v3t38_incomplete_runtime_cannot_make_reuse_key(tmp_path):
    from backend.app.perception_identity import capture_inputs, layered_identities
    p=tmp_path/'source';p.write_bytes(b'source')
    inputs=capture_inputs(p,model_path=None,tracker_path=tmp_path/'missing.yaml')
    layers=layered_identities(inputs,inputs,{}, {},runtime_build=None)
    assert all(value['digest'] is None and not value['reusable'] for value in layers.values())


def test_v3t36_embedded_profile_references_are_bound_by_content(tmp_path,monkeypatch):
    from backend.app import perception_identity as pi
    from backend.app import edge_share_repair_profiles as profiles
    path=tmp_path/'input';path.write_bytes(b'input')
    weights=tmp_path/'w.pt';weights.write_bytes(b'weights')
    seed=tmp_path/'audit.json';seed.write_text('{"selected":1}')
    monkeypatch.setattr(profiles,'get_source_edge_share_repair_config',lambda _: {'enabled':True,'auditMatrixPath':str(seed)})
    def snap():return pi.capture_inputs(path,model_path=str(weights),repair_profile='same-profile')
    before=snap();seed.write_text('{"selected":2}');after=snap()
    assert before['primary']==after['primary']
    assert before['recovery']!=after['recovery']


def test_v3t36_source_name_gated_recovery_is_not_a_primary_change(tmp_path):
    from backend.app.perception_identity import capture_inputs
    left=tmp_path/'target.mp4';left.write_bytes(b'identical')
    right=tmp_path/'other.mp4';right.write_bytes(b'identical')
    a=capture_inputs(left,model_path=None);b=capture_inputs(right,model_path=None)
    assert a['primary']==b['primary'] and a['recovery']!=b['recovery']
