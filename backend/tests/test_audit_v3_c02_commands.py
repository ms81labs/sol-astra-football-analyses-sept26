"""C02 semantic-command checkpoint. Synthetic observations, no model inference."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.processor import reprocess_video_match
from backend.app.schemas import ColorClusterSummary
from backend.app.storage import Storage
from backend.tests.test_audit_v2_h02_review import (
    install_raw_row_match, install_tracking_match, _team_for_track,
)

pytestmark = pytest.mark.integration


def client_store(tmp_path):
    app = create_app(storage_root=tmp_path / 'storage')
    return TestClient(app, base_url='http://127.0.0.1', raise_server_exceptions=False), app.state.storage


def state(storage, mid):
    return (storage.current_generation(mid).generationId,
            storage.get_match(mid).config.model_dump(mode='json'),
            storage.list_corrections(mid))


def test_v3t10_patch_after_applied_review_survives_other_edit_and_restart(tmp_path):
    client, storage = client_store(tmp_path)
    mid = install_raw_row_match(storage, tmp_path)
    rows = storage.load_raw_rows(mid)
    for row in rows:
        if row['Entity_Type'] == 'ball':
            row['X'] = [91., 92., 50., 48.][min(row['Frame_ID'], 3)]
        else:
            row['X'] = 90. if row['Track_ID'] == 7 else 10.
        row['Y'] = 34.
    storage.save_raw_rows(mid, rows)
    reprocess_video_match(storage, mid)
    event = next(e for e in storage.load_events(mid) if e.type == 'shot')
    storage.submit_correction(mid, kind='event_accept', payload={'eventId': event.eventId})
    response = client.patch(f'/api/matches/{mid}/config', json={
        'myTeamCluster': 1, 'attackDirection': 'right_to_left',
    })
    assert response.status_code == 200, response.text
    assert response.json()['config']['myTeamCluster'] == 1
    assert _team_for_track(storage, mid, 7) == 'enemy'
    storage.submit_correction(mid, kind='playlist_item', payload={'label': 'unrelated'})
    reprocess_video_match(storage, mid)
    assert _team_for_track(storage, mid, 7) == 'enemy'
    assert storage.get_match(mid).config.attackDirection == 'right_to_left'
    env = {**os.environ, 'PYTHON_DOTENV_DISABLED': '1'}
    result = subprocess.run([sys.executable, '-c',
        'import sys; from backend.app.storage import Storage; s=Storage(sys.argv[1]); '
        'm=s.get_match(sys.argv[2]); f=s.load_frames(m.id)[0]; '
        'assert m.config.myTeamCluster==1; assert m.config.attackDirection=="right_to_left"; '
        'assert any(p.id==7 for p in f.enemies)',
        str(storage.storage_root), mid], env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_v3t12_ambiguous_three_cluster_swap_is_nonmutating_422(tmp_path):
    client, storage = client_store(tmp_path)
    mid = install_raw_row_match(storage, tmp_path)
    match = storage.get_match(mid)
    storage.update_match_status(mid, status='ready', team_clusters=[*match.teamClusters,
        ColorClusterSummary(clusterId=2, rgbCentroid=[0.,255.,0.], trackIds=[99])])
    before = state(storage, mid)
    response = client.post(f'/api/matches/{mid}/corrections', json={
        'kind': 'team_mapping', 'payload': {'swap': True}})
    assert response.status_code == 422, response.text
    assert response.json()['error'] == 'AMBIGUOUS_TEAM_SWAP'
    assert state(storage, mid) == before


def test_v3t11_stale_explicit_generation_rejected_at_api(tmp_path):
    client, storage = client_store(tmp_path)
    mid = install_raw_row_match(storage, tmp_path)
    old = storage.current_generation(mid).generationId
    storage.submit_correction(mid, kind='team_mapping', payload={'swap': True})
    before = state(storage, mid)
    response = client.post(f'/api/matches/{mid}/corrections', json={
        'kind': 'team_mapping', 'payload': {'swap': True}, 'baseGeneration': old})
    assert response.status_code == 409, response.text
    assert state(storage, mid) == before


@pytest.mark.parametrize('mode', ['video', 'tracking'])
def test_v3t13_swap_then_undo_is_a_positive_control(tmp_path, mode):
    _client, storage = client_store(tmp_path)
    mid = install_raw_row_match(storage, tmp_path) if mode == 'video' else install_tracking_match(storage)
    before = _team_for_track(storage, mid, 7)
    command = storage.submit_correction(mid, kind='team_mapping', payload={'swap': True})
    assert _team_for_track(storage, mid, 7) != before
    storage.undo_correction(mid, command.correctionId)
    reprocess_video_match(storage, mid)
    assert _team_for_track(Storage(storage.storage_root), mid, 7) == before


def test_v3t20_undo_split_with_dependent_join_conflicts(tmp_path):
    client, storage = client_store(tmp_path)
    mid = install_tracking_match(storage)
    split = storage.submit_correction(mid, kind='track_split',
        payload={'trackId': '7', 'atFrame': 1, 'newTrackId': 70})
    storage.submit_correction(mid, kind='track_join',
        payload={'leftTrackId': '7', 'rightTrackId': '70'})
    before = state(storage, mid)
    response = client.post(f'/api/matches/{mid}/corrections/{split.correctionId}/undo')
    assert response.status_code == 409, response.text
    assert response.json()['error'] == 'COMMAND_DEPENDENCY_CONFLICT'
    assert state(storage, mid) == before


def test_v3t14_explicit_pair_targets_and_undo_with_three_clusters(tmp_path):
    client, storage = client_store(tmp_path)
    mid = install_raw_row_match(storage, tmp_path)
    clusters = storage.get_match(mid).teamClusters
    storage.update_match_status(mid, status='ready', team_clusters=[*clusters,
        ColorClusterSummary(clusterId=2, rgbCentroid=[0.,255.,0.], trackIds=[99])])
    def submit(payload):
        r = client.post(f'/api/matches/{mid}/corrections', json={'kind': 'team_mapping', 'payload': payload})
        assert r.status_code == 200, r.text
        return r.json()
    first = submit({'swap': True, 'pair': [0,2]})
    assert first['payload']['targetCluster'] == 2
    assert first['payload']['expectedSourceSelection'] == 0
    assert storage.get_match(mid).config.myTeamCluster == 2
    submit({'swap': True, 'pair': [0,2]})
    assert storage.get_match(mid).config.myTeamCluster == 0
    selected = submit({'targetCluster': 1})
    assert _team_for_track(storage, mid, 7) == 'enemy'
    assert client.post(f"/api/matches/{mid}/corrections/{selected['correctionId']}/undo").status_code == 200
    assert storage.get_match(mid).config.myTeamCluster == 0
    swapped = submit({'swap': True, 'pair': [0,2]})
    assert client.post(f"/api/matches/{mid}/corrections/{swapped['correctionId']}/undo").status_code == 200
    assert storage.get_match(mid).config.myTeamCluster == 0


@pytest.mark.parametrize('route', ['config', 'corrections'])
def test_v3t20_idempotent_delivery_is_not_a_second_apply(tmp_path, route):
    client, storage = client_store(tmp_path)
    mid = install_raw_row_match(storage, tmp_path)
    body = {'commandId': 'stable-command', 'idempotencyKey': 'stable-key',
            'expectedVersion': 0, 'baseGeneration': storage.current_generation(mid).generationId}
    if route == 'config':
        body['myTeamCluster'] = 1
        method = client.patch
    else:
        body.update(kind='team_mapping', payload={'swap': True})
        method = client.post
    url = f'/api/matches/{mid}/{route}'
    first = method(url, json=body)
    assert first.status_code == 200, first.text
    before = state(storage, mid)
    second = method(url, json=body)
    assert second.status_code == 200, second.text
    assert state(storage, mid) == before
    if route == 'config':
        body['myTeamCluster'] = 0
    else:
        body['payload'] = {'targetCluster': 0}
    conflicting = method(url, json=body)
    assert conflicting.status_code == 409, conflicting.text
    assert conflicting.json()['error'] == 'IDEMPOTENCY_CONFLICT'
    assert state(storage, mid) == before


@pytest.mark.parametrize('body', [
    {'calibrationCommitted': True}, {'unknownConfig': 'injected'},
    {'myTeamCluster': 999}, {'myTeamCluster': True}, {'myTeamCluster': '1'},
    {'myTeamCluster': 1, 'rights': {'cloudPermission': True}},
    {'attackDirection': 'right_to_left', 'homeTeam': 'mixed'},
    {'attackDirection': 'diagonal'},
])
def test_v3t15_invalid_or_mixed_config_is_atomic(tmp_path, body):
    client, storage = client_store(tmp_path)
    mid = install_raw_row_match(storage, tmp_path)
    before = state(storage, mid)
    response = client.patch(f'/api/matches/{mid}/config', json=body)
    assert response.status_code == 422, response.text
    assert state(storage, mid) == before


@pytest.mark.parametrize('control', [{'expectedVersion': 99}, {'baseGeneration': 'gen_stale'},
                                    {'expectedVersion': True}, {'expectedVersion': -1}])
def test_v3t11_config_checks_expected_controls_before_recording(tmp_path, control):
    client, storage = client_store(tmp_path)
    mid = install_raw_row_match(storage, tmp_path)
    before = state(storage, mid)
    response = client.patch(f'/api/matches/{mid}/config', json={'myTeamCluster': 1, **control})
    assert response.status_code in {409,422}, response.text
    assert state(storage, mid) == before


def test_v3t15_failed_candidate_keeps_pointer_config_rights_and_original_rows(tmp_path, monkeypatch):
    from backend.app.review_service import ReviewService
    client, storage = client_store(tmp_path)
    mid = install_raw_row_match(storage, tmp_path)
    before = state(storage, mid)
    raw = storage.storage_root / 'matches' / mid / 'raw_rows.json'
    original_hash = hashlib.sha256(raw.read_bytes()).hexdigest()
    def fail(*args, **kwargs):
        raise RuntimeError('controlled candidate failure')
    monkeypatch.setattr(ReviewService, '_materialize', fail)
    response = client.patch(f'/api/matches/{mid}/config', json={'myTeamCluster': 1})
    assert response.status_code == 500, response.text
    assert storage.current_generation(mid).generationId == before[0]
    assert storage.get_match(mid).config.model_dump(mode='json') == before[1]
    assert hashlib.sha256(raw.read_bytes()).hexdigest() == original_hash
    # Failed command is retained as a failed receipt, never as applied state.
    assert storage.list_corrections(mid)[-1]['applyState'] == 'failed'


def test_undo_of_undo_is_explicitly_unsupported(tmp_path):
    client, storage = client_store(tmp_path)
    mid = install_tracking_match(storage)
    command = storage.submit_correction(mid, kind='team_mapping', payload={'swap': True})
    undone = storage.undo_correction(mid, command.correctionId)
    before = state(storage, mid)
    response = client.post(f'/api/matches/{mid}/corrections/{undone.correctionId}/undo')
    assert response.status_code == 409, response.text
    assert response.json()['error'] == 'REDO_UNSUPPORTED'
    assert state(storage, mid) == before


def test_analytical_undo_does_not_restore_old_policy_or_names(tmp_path):
    client, storage = client_store(tmp_path)
    mid = install_raw_row_match(storage, tmp_path)
    old = storage.current_generation(mid).generationId
    result = client.patch(f'/api/matches/{mid}/config', json={'myTeamCluster': 1})
    assert result.status_code == 200, result.text
    command_id = result.json()['correction']['correctionId']
    assert client.patch(f'/api/matches/{mid}/config', json={
        'rights': {'cloudPermission': True, 'processingScope': 'local_only'}, 'homeTeam': 'Renamed'}).status_code == 200
    assert client.post(f'/api/matches/{mid}/corrections/{command_id}/undo').status_code == 200
    match = storage.get_match(mid)
    assert match.config.myTeamCluster == 0
    assert match.config.rights.cloudPermission is True
    assert match.config.homeTeam == 'Renamed'
    with storage.generation_snapshot(mid, generation_id=old):
        assert storage.get_match(mid).config.rights.cloudPermission is True


def test_generic_correction_cannot_inject_an_accepted_calibration(tmp_path):
    client, storage = client_store(tmp_path)
    mid = install_raw_row_match(storage, tmp_path)
    before = state(storage, mid)
    response = client.post(f'/api/matches/{mid}/corrections', json={
        'kind': 'calibration', 'payload': {'revision': {'accepted': True, 'measured': True}}})
    assert response.status_code == 422
    assert response.json()['error'] == 'CALIBRATION_COMMIT_REQUIRED'
    assert state(storage, mid) == before


def test_v3t11_explicit_tracking_roles_and_stale_service_call(tmp_path):
    from backend.app.generations import StaleGeneration
    from backend.app.review_service import ReviewService
    _client, storage = client_store(tmp_path)
    mid = install_tracking_match(storage)
    old = storage.current_generation(mid).generationId
    selected = storage.submit_correction(mid, kind='team_mapping', payload={'targetRole': 'enemy'})
    assert selected.payload['targetRole'] == 'enemy'
    assert _team_for_track(storage, mid, 7) == 'enemy'
    storage.submit_correction(mid, kind='team_mapping', payload={'swap': True})
    assert _team_for_track(storage, mid, 7) == 'my_team'
    before = state(storage, mid)
    with pytest.raises(StaleGeneration):
        ReviewService(storage).submit(mid, kind='team_mapping', payload={'swap': True},
            author='analyst', expected_version=None, base_generation=old)
    assert state(storage, mid) == before


def test_idempotent_historical_config_receipt_does_not_invalidate_newer_report(tmp_path):
    client, storage = client_store(tmp_path)
    mid = install_raw_row_match(storage, tmp_path)
    url = f'/api/matches/{mid}/config'
    body = {'myTeamCluster': 1, 'commandId': 'first-selection'}
    first = client.patch(url, json=body)
    assert first.status_code == 200
    first_gen = first.json()['generationId']
    assert client.patch(url, json={'myTeamCluster': 0}).status_code == 200
    storage.save_analysis_artifact(mid, 'tactical_report', {'newer': True})
    before = state(storage, mid)
    response = client.patch(url, json=body)
    assert response.status_code == 200, response.text
    assert response.json()['generationId'] == first_gen
    assert response.json()['config']['myTeamCluster'] == 1
    assert state(storage, mid) == before
    assert storage.load_analysis_artifact(mid, 'tactical_report') == {'newer': True}


def test_uncommitted_request_recovery_cannot_bypass_a_newer_generation(tmp_path):
    client, storage = client_store(tmp_path)
    mid = install_raw_row_match(storage, tmp_path)
    pending = storage.submit_correction(mid, kind='team_mapping', payload={'swap': True}, crash_before_commit=True)
    storage.submit_correction(mid, kind='team_mapping', payload={'targetCluster': 1})
    before = state(storage, mid)
    response = client.post(f'/api/matches/{mid}/corrections/{pending.correctionId}/recover')
    assert response.status_code == 409, response.text
    assert state(storage, mid) == before
    assert storage.list_corrections(mid, state='pending')[0]['applyState'] == 'received'


def test_recovered_pending_command_gets_next_log_version(tmp_path):
    _client, storage = client_store(tmp_path)
    mid = install_tracking_match(storage)
    first = storage.submit_correction(mid, kind='team_mapping', payload={'swap': True})
    pending = storage.submit_correction(mid, kind='team_mapping', payload={'swap': True}, crash_before_commit=True)
    recovered = storage.recover_correction(mid, pending.correctionId)
    assert recovered.version == first.version + 1
    assert recovered.applyState == 'applied'
    assert _team_for_track(storage, mid, 7) == 'my_team'


@pytest.mark.parametrize('payload', [[], 'swap', 1, None])
def test_nonobject_command_payload_fails_validation(tmp_path, payload):
    client, storage = client_store(tmp_path)
    mid = install_tracking_match(storage)
    before = state(storage, mid)
    response = client.post(f'/api/matches/{mid}/corrections', json={'kind': 'team_mapping', 'payload': payload})
    assert response.status_code == 422, response.text
    assert state(storage, mid) == before


def test_selection_updates_ready_status_with_its_generation(tmp_path):
    client, storage = client_store(tmp_path)
    mid = install_raw_row_match(storage, tmp_path)
    storage.update_match_status(mid, status='ready', requires_team_selection=True,
                                team_clusters=storage.get_match(mid).teamClusters)
    response = client.patch(f'/api/matches/{mid}/config', json={'myTeamCluster': 1})
    assert response.status_code == 200, response.text
    assert response.json()['requiresTeamSelection'] is False


def test_legacy_bare_swap_freezes_proven_target_without_rewriting_history(tmp_path):
    from backend.app.schemas import MatchConfig
    from backend.app.workbench.review import new_correction
    from backend.app.workbench.identity import apply_team_swap
    client, storage = client_store(tmp_path)
    mid = install_raw_row_match(storage, tmp_path)
    original = storage.get_match(mid)
    root = storage.storage_root / 'matches' / mid
    storage._write_json(root / 'review_base_config.json', original.config.model_dump(mode='json'))
    legacy = new_correction(mid, 'team_mapping', {'swap': True}).model_copy(update={'schemaVersion': 1})
    log = storage._load_correction_log(mid)
    old = log.submit(legacy)
    storage._save_correction_log(mid, log)
    summary, assignments, formations, shots = storage.load_analytics(mid)
    ref = storage.publish_generation(mid, frames=apply_team_swap(storage.load_frames(mid)), summary=summary,
        assignments=assignments, formation_timeline=formations, shots=shots, events=storage.load_events(mid),
        correction_head=old.correctionId, effective_config=MatchConfig(myTeamCluster=1), include_pending_commands=True)
    log.update(old.correctionId, applyState='applied', appliedGeneration=ref.generationId)
    storage._save_correction_log(mid, log)
    old_payload = dict(log.history(mid)[0].payload)
    storage.update_match_status(mid, status='ready', team_clusters=[*original.teamClusters,
        ColorClusterSummary(clusterId=2, rgbCentroid=[0.,255.,0.], trackIds=[99])])
    response = client.patch(f'/api/matches/{mid}/config', json={'attackDirection': 'right_to_left'})
    assert response.status_code == 200, response.text
    assert response.json()['config']['myTeamCluster'] == 1
    assert _team_for_track(storage, mid, 7) == 'enemy'
    assert storage.list_corrections(mid)[0]['payload'] == old_payload
    receipt = json.loads((root / 'review_command_migrations.json').read_text())
    assert receipt['resolved'][old.commandId]['targetCluster'] == 1
    assert receipt['resolved'][old.commandId]['appliedGeneration'] == ref.generationId
    storage.undo_correction(mid, old.correctionId)
    assert _team_for_track(storage, mid, 7) == 'my_team'


def test_failed_request_recovery_cannot_bypass_a_newer_generation(tmp_path, monkeypatch):
    from backend.app.review_service import ReviewService
    client, storage = client_store(tmp_path)
    mid = install_raw_row_match(storage, tmp_path)
    materialise = ReviewService._materialize
    def fail(*_args, **_kwargs):
        raise RuntimeError('synthetic pre-publication failure')
    monkeypatch.setattr(ReviewService, '_materialize', fail)
    response = client.patch(f'/api/matches/{mid}/config', json={
        'myTeamCluster': 1, 'commandId': 'failed-selection'})
    assert response.status_code >= 400
    failed = storage.list_corrections(mid)[-1]
    assert failed['applyState'] == 'failed'
    monkeypatch.setattr(ReviewService, '_materialize', materialise)
    assert client.patch(f'/api/matches/{mid}/config', json={'attackDirection': 'right_to_left'}).status_code == 200
    before = state(storage, mid)
    response = client.post(f"/api/matches/{mid}/corrections/{failed['correctionId']}/recover")
    assert response.status_code == 409, response.text
    assert state(storage, mid) == before


@pytest.mark.parametrize('payload', [[], [('swap', True)], 'swap', 1])
def test_storage_boundary_does_not_coerce_nonobject_commands(tmp_path, payload):
    from backend.app.semantic_commands import SemanticCommandError
    _client, storage = client_store(tmp_path)
    mid = install_tracking_match(storage)
    before = state(storage, mid)
    with pytest.raises(SemanticCommandError, match='must be an object'):
        storage.submit_correction(mid, kind='team_mapping', payload=payload)
    assert state(storage, mid) == before


@pytest.mark.parametrize('target', [[], {}, True])
def test_tracking_role_type_is_validated_before_admission(tmp_path, target):
    client, storage = client_store(tmp_path)
    mid = install_tracking_match(storage)
    before = state(storage, mid)
    response = client.post(f'/api/matches/{mid}/corrections', json={
        'kind': 'team_mapping', 'payload': {'targetRole': target}})
    assert response.status_code == 422
    assert response.json()['error'] == 'INVALID_TEAM_MAPPING'
    assert state(storage, mid) == before


@pytest.mark.parametrize('invalid', [float('nan'), float('inf')])
def test_nonfinite_command_is_rejected_before_digest_or_log_write(tmp_path, invalid):
    from backend.app.semantic_commands import SemanticCommandError
    _client, storage = client_store(tmp_path)
    mid = install_tracking_match(storage)
    before = state(storage, mid)
    with pytest.raises(SemanticCommandError, match='finite JSON'):
        storage.submit_correction(mid, kind='playlist_item', payload={'time': invalid})
    assert state(storage, mid) == before
