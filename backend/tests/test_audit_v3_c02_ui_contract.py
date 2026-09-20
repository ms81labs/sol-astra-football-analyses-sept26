"""C02 lifecycle panes and legacy physical facts: real storage/API boundaries."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.storage import Storage
from backend.tests.test_audit_v3_c02_identity import tracking
from backend.tests.test_dashboard import _seed_dashboard_storage

pytestmark = pytest.mark.integration
PHYSICAL_FIELDS = ('myTeamDistance', 'enemyDistance', 'myTeamTopSpeed', 'enemyTopSpeed', 'myTeamSprints', 'enemySprints')


def inventory(root: Path) -> dict[str, str]:
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*.json') if path.is_file()}


def test_legacy_summary_does_not_publish_unscoped_physical_totals(tmp_path):
    root = tmp_path / 'store'
    ids = _seed_dashboard_storage(root, [dict(name='Legacy', possession=55, myTeamXg=1.2,
        enemyXg=.8, myTeamSprints=12, enemySprints=8, formation='4-3-3')])
    s = Storage(root)
    mid = ids[0]
    before = inventory(root / 'matches')
    assert s.identity_eligibility(mid)['continuous'] is False
    for summary in (s.load_analytics(mid)[0].model_dump(), s.list_matches_with_analytics()[0]['summary']):
        assert all(summary[key] is None for key in PHYSICAL_FIELDS)
        assert summary['possession'] == 55  # Do not erase unrelated valid measurements.
        assert summary['myTeamXg'] == 1.2
    assert inventory(root / 'matches') == before  # Compatibility is a read view, not rewriting history.


@pytest.mark.parametrize('suffix', ['/quality', '/incidents/review', '/setup', '/setup/preview', '/metrics/inspect/my_team_distance_m'])
def test_auxiliary_panes_echo_and_honour_selected_generation(tmp_path, suffix):
    app = create_app(storage_root=tmp_path / 'store')
    s = app.state.storage
    mid = tracking(s, tmp_path)
    old = s.current_generation(mid).generationId
    s.submit_correction(mid, kind='track_split', payload={'trackId': '7', 'atFrame': 5, 'newTrackId': 99})
    with TestClient(app, base_url='http://127.0.0.1') as client:
        response = client.get(f'/api/matches/{mid}{suffix}', params={'generationId': old})
        assert response.status_code == 200, response.text
        assert response.json()['generationId'] == old
        missing = client.get(f'/api/matches/{mid}{suffix}', params={'generationId': 'nonexistent'})
        assert missing.status_code != 200  # No silent fallback to the current generation.


@pytest.mark.parametrize('operation', ['promote', 'repair'])
def test_identity_routes_reject_stale_ui_generation_without_command_admission(tmp_path, operation):
    app = create_app(storage_root=tmp_path / 'store')
    s = app.state.storage
    mid = tracking(s, tmp_path)
    old = s.current_generation(mid).generationId
    s.submit_correction(mid, kind='config_set', payload={'values': {'attackDirection': 'right_to_left'}})
    before = (s.current_generation(mid).generationId, s.list_corrections(mid))
    body = {'baseGeneration': old, 'commandId': f'ui-{operation}'}
    body.update({'reviewed': True} if operation == 'promote' else {'kind': 'track_split', 'trackId': '7', 'atFrame': 5})
    with TestClient(app, base_url='http://127.0.0.1') as client:
        response = client.post(f'/api/matches/{mid}/identity/{operation}', json=body)
    assert response.status_code == 409, response.text
    assert (s.current_generation(mid).generationId, s.list_corrections(mid)) == before


@pytest.mark.parametrize('operation', ['repair', 'promote', 'calibration/commit'])
def test_identity_and_calibration_route_retries_return_original_receipt(tmp_path, operation):
    from backend.tests.test_audit_v3_c02_projection import profile
    app = create_app(storage_root=tmp_path / 'store')
    store = app.state.storage
    mid = tracking(store, tmp_path)
    base = store.current_generation(mid).generationId
    body = ({'kind': 'track_split', 'trackId': '7', 'atFrame': 5} if operation == 'repair'
            else {'reviewed': True} if operation == 'promote' else profile().model_dump(mode='json'))
    body.update(baseGeneration=base, commandId='retry-ui-command')
    path = f'/api/matches/{mid}/' + (f'identity/{operation}' if '/' not in operation else operation)
    with TestClient(app, base_url='http://127.0.0.1') as client:
        first = client.post(path, json=body)
        assert first.status_code == 200, first.text
        first = first.json()['correction']
        before = inventory(store.storage_root / 'matches')
        repeated = client.post(path, json=body)
        assert repeated.status_code == 200, repeated.text
        assert repeated.json()['correction'] == first
        assert inventory(store.storage_root / 'matches') == before


def test_ui_metadata_uses_the_selected_generation_not_newer_command_history(tmp_path):
    app = create_app(storage_root=tmp_path / 'store')
    s = app.state.storage
    mid = tracking(s, tmp_path)
    approval = s.promote_identity_for_match(mid, {'reviewed': True})['correction']
    old = s.current_generation(mid).generationId
    old_manifest, _ = s.generations.manifest(mid, old)
    s.submit_correction(mid, kind='track_split', payload={'trackId': '7', 'atFrame': 5, 'newTrackId': 99})
    new = s.current_generation(mid).generationId
    with TestClient(app, base_url='http://127.0.0.1') as client:
        detail = client.get(f'/api/matches/{mid}', params={'generationId': old}).json()
        assert detail['includedCommandIds'] == old_manifest.includedCommandIds
        assert len(detail['includedCommandIds']) < len(client.get(f'/api/matches/{mid}').json()['includedCommandIds'])
        heatmap = client.get(f'/api/matches/{mid}/heatmap', params={'generationId': old}).json()
        assert heatmap['withheld'] is False
        assert heatmap['pitchDimensions'] == {'pitchLengthM': 100.0, 'pitchWidthM': 60.0}
        assert client.get(f'/api/matches/{mid}/heatmap', params={'generationId': new}).json()['withheld'] is True
    assert approval['applyState'] == 'applied'


def test_legacy_dashboard_comparison_withholds_both_missing_sprint_totals(tmp_path):
    """C02 legacy filtering must not crash the multi-match aggregate endpoint."""
    root = tmp_path / 'store'
    _seed_dashboard_storage(root, [
        dict(name='Alpha', possession=55, myTeamXg=1.2, enemyXg=.8,
             myTeamSprints=12, enemySprints=8, formation='4-3-3'),
        dict(name='Beta', possession=48, myTeamXg=.9, enemyXg=1.1,
             myTeamSprints=9, enemySprints=11, formation='4-4-2'),
    ])
    app = create_app(storage_root=root)
    before = inventory(root / 'matches')
    with TestClient(app, base_url='http://127.0.0.1') as client:
        response = client.get('/api/aggregate/dashboard')
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['summary']['matchCount'] == 2
    for name in ('avgMyTeamSprints', 'avgEnemySprints'):
        assert data['summary'][name] is None
    assert data['comparison']['myTeamSprintsDelta'] is None
    assert data['comparison']['enemySprintsDelta'] is None
    assert data['comparison']['possessionDelta'] == -7.
    assert data['comparison']['xgDiffDelta'] == -.6
    for trend in data['trends']:
        summary = trend['summary']
        assert all(summary[name] is None for name in PHYSICAL_FIELDS)
        records = {item['metric']: item for item in summary['metricAvailability']}
        for metric in ('my_team_sprints', 'enemy_sprints', 'my_team_distance_m', 'enemy_distance_m',
                       'my_team_top_speed_kmh', 'enemy_top_speed_kmh'):
            assert records[metric]['availability'] == 'withheld'
            assert records[metric]['value'] is None
            assert 'IDENTITY_APPROVAL_UNSCOPED' in records[metric]['reasonCodes']
    assert inventory(root / 'matches') == before


def test_dashboard_scoped_zero_sprints_remain_measured_and_partial_review_withholds_delta(tmp_path):
    """Real C02 processing/approval supplies the positive zero control, not an injected flag."""
    app = create_app(storage_root=tmp_path / 'store')
    storage = app.state.storage
    ids = []
    for name in ('first', 'second'):
        directory = tmp_path / name
        directory.mkdir()
        mid = tracking(storage, directory)
        storage.promote_identity_for_match(mid, {'reviewed': True})
        ids.append(mid)
    with TestClient(app, base_url='http://127.0.0.1') as client:
        response = client.get('/api/aggregate/dashboard')
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload['summary']['avgMyTeamSprints'] == 0.
        assert payload['summary']['avgEnemySprints'] == 0.
        assert payload['comparison']['myTeamSprintsDelta'] == 0.
        assert payload['comparison']['enemySprintsDelta'] == 0.
        storage.submit_correction(ids[1], kind='track_split', payload={'trackId': '7', 'atFrame': 5, 'newTrackId': 99})
        changed = client.get('/api/aggregate/dashboard').json()
        # Average only the still-admitted match, not an invented zero for the other.
        assert changed['summary']['avgMyTeamSprints'] == 0.
        assert changed['comparison']['myTeamSprintsDelta'] is None
        assert changed['comparison']['enemySprintsDelta'] is None


def test_dashboard_aggregate_positive_numbers_and_zero_share_nullable_reader():
    from backend.app.main import _dashboard_average, _dashboard_difference

    previous = {'myTeamSprints': 12}
    current = {'myTeamSprints': 9}
    assert _dashboard_average([previous, current], field='myTeamSprints', metric='my_team_sprints') == 10.5
    assert _dashboard_difference(current, previous, field='myTeamSprints', metric='my_team_sprints') == -3.
    assert _dashboard_difference({'myTeamSprints': 0}, {'myTeamSprints': 0}, field='myTeamSprints', metric='my_team_sprints') == 0.
    for invalid in (None, True, '12', float('nan'), float('inf')):
        invalid_summary = {'myTeamSprints': invalid}
        assert _dashboard_difference(current, invalid_summary, field='myTeamSprints', metric='my_team_sprints') is None
        assert _dashboard_average([invalid_summary], field='myTeamSprints', metric='my_team_sprints') is None
    withheld = {'myTeamSprints': 100, 'metricAvailability': [
        {'metric': 'my_team_sprints', 'availability': 'withheld', 'value': 100}]}
    assert _dashboard_difference(current, withheld, field='myTeamSprints', metric='my_team_sprints') is None
    assert _dashboard_average([current, withheld], field='myTeamSprints', metric='my_team_sprints') == 9.
