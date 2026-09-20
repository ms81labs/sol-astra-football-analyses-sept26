from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app import llm
from backend.app.main import create_app
from backend.app.report_export import render_match_report_html
from backend.app.schemas import FrameData, MatchConfig, MatchSummary


@pytest.fixture
def api(tmp_path):
    app = create_app(storage_root=tmp_path / 'storage')
    with TestClient(app, base_url='http://127.0.0.1', raise_server_exceptions=False) as client:
        yield app.state.storage, client, app


def make_match(storage, input_mode='video'):
    path = storage.save_upload('input.json', b'[]')
    match = storage.create_match('Test', input_mode, 'input.json', path, MatchConfig())
    return storage.update_match_status(match.id, status='ready')


def publish_minimal_generation(storage, match_id, frames):
    # C01 fixture admission is explicit; ordinary provider reads never migrate.
    storage.publish_generation(
        match_id, frames=frames,
        summary=MatchSummary(
            possession=None, myTeamDistance=None, enemyDistance=None,
            myTeamTopSpeed=None, enemyTopSpeed=None,
            myTeamSprints=None, enemySprints=None,
        ),
        assignments=[], formation_timeline=[], shots=[], events=[],
        correction_head="none",
    )


@pytest.mark.parametrize('payload', [
    {'attackDirection': 'invalid'}, {'myTeamCluster': []}, {'myTeamCluster': {}},
    {'myTeamCluster': True}, {'myTeamCluster': '1'}, {'myTeamCluster': 1.5},
])
def test_config_rejects_invalid_types_without_mutation(api, payload):
    storage, client, _ = api
    match = make_match(storage)
    response = client.patch(f'/api/matches/{match.id}/config', json=payload)
    assert response.status_code == 422
    assert storage.get_match(match.id) == match


def test_failed_reprocessing_restores_outputs_and_config(api, monkeypatch):
    storage, client, _ = api
    match = make_match(storage)
    storage.save_analysis_artifact(match.id, 'analytics', {'previous': True})

    def fail_after_output_write(inner_storage, match_id, **kwargs):
        inner_storage.save_analysis_artifact(match_id, 'analytics', {'partial': True})
        inner_storage.save_analysis_artifact(match_id, 'events', {'partial': True})
        raise FileNotFoundError('required later artifact')

    monkeypatch.setattr('backend.app.main.reprocess_video_match', fail_after_output_write)
    response = client.patch(f'/api/matches/{match.id}/config', json={'myTeamCluster': 1})
    assert response.status_code == 409
    assert storage.get_match(match.id) == match
    assert storage.load_analysis_artifact(match.id, 'analytics') == {'previous': True}
    assert not (storage.storage_root / 'matches' / match.id / 'events.json').exists()


def test_config_publication_failure_restores_reprocessed_outputs(api, monkeypatch):
    storage, client, _ = api
    match = make_match(storage)
    storage.save_analysis_artifact(match.id, 'analytics', {'previous': True})
    original_update = storage.update_match_config

    def fail_after_config_write(match_id, config):
        original_update(match_id, config)
        raise OSError('commit acknowledgement failed')

    def reprocess(inner_storage, match_id, **kwargs):
        inner_storage.save_analysis_artifact(match_id, 'analytics', {'new': True})

    monkeypatch.setattr(storage, 'update_match_config', fail_after_config_write)
    monkeypatch.setattr('backend.app.main.reprocess_video_match', reprocess)
    response = client.patch(f'/api/matches/{match.id}/config', json={'myTeamCluster': 1})
    assert response.status_code >= 400
    assert storage.get_match(match.id) == match
    assert storage.load_analysis_artifact(match.id, 'analytics') == {'previous': True}


@pytest.mark.parametrize('input_mode', ['video', 'tracking_json'])
def test_direction_update_reprocesses_with_candidate_before_config_publication(api, monkeypatch, input_mode):
    storage, client, _ = api
    match = make_match(storage, input_mode)
    received = []

    publish_minimal_generation(storage, match.id, [])
    from backend.app.review_service import ReviewService
    original = ReviewService._materialize

    def materialize(service, match_id, config, commands):
        # Candidate analytical inputs are visible only within the candidate;
        # the authoritative SQL projection still belongs to the old generation.
        assert service.storage.get_match(match_id).config.attackDirection == 'right_to_left'
        with service.storage._connect() as connection:
            row = connection.execute("SELECT config_json FROM matches WHERE id=?", (match_id,)).fetchone()
        assert json.loads(row["config_json"])["attackDirection"] == "left_to_right"
        received.append(config.attackDirection)
        return original(service, match_id, config, commands)

    monkeypatch.setattr(ReviewService, '_materialize', materialize)
    response = client.patch(f'/api/matches/{match.id}/config', json={'attackDirection': 'right_to_left'})
    assert response.status_code == 200
    assert received == ['right_to_left']
    assert storage.get_match(match.id).config.attackDirection == 'right_to_left'


@pytest.mark.parametrize('kind,fields', [('annotations', {'type': 'note'}), ('issues', {'bucket': 'tracking', 'note': 'bad'})])
def test_missing_match_review_writes_do_not_create_artifacts(api, kind, fields):
    storage, client, _ = api
    payload = dict(frameStart=0, frameEnd=1, timestampStart=0, timestampEnd=1, **fields)
    assert client.post(f'/api/matches/missing/{kind}', json=payload).status_code == 404
    assert client.delete(f'/api/matches/missing/{kind}/missing').status_code == 404
    assert not (storage.storage_root / 'matches' / 'missing').exists()


def test_disconnected_queued_job_websocket_stops_polling(api, monkeypatch):
    storage, _, app = api
    match = make_match(storage)
    job = storage.create_job(match.id)
    original = storage.get_job
    polls = []

    def get_job(job_id):
        polls.append(job_id)
        return original(job_id)

    monkeypatch.setattr(storage, 'get_job', get_job)

    async def probe():
        messages = iter([{'type': 'websocket.connect'}, {'type': 'websocket.disconnect', 'code': 1000}])

        async def receive():
            return next(messages)

        async def send(message):
            pass

        await asyncio.wait_for(app({
            'type': 'websocket', 'asgi': {'version': '3.0', 'spec_version': '2.4'},
            'http_version': '1.1', 'scheme': 'ws', 'server': ('127.0.0.1', 80),
            'client': ('127.0.0.1', 1234), 'root_path': '', 'path': f'/ws/jobs/{job.id}',
            'query_string': b'', 'headers': [(b'host', b'127.0.0.1')], 'subprotocols': [], 'state': {},
        }, receive, send), timeout=1.2)

    asyncio.run(probe())
    assert len(polls) <= 1


REPORT = {'summary': 'OK', 'attacking': 'OK', 'defensive': 'OK', 'pressing': 'OK',
          'weaknesses': 'OK', 'key_player': 7, 'rating': 8}


@pytest.mark.parametrize('provider', ['local', 'cloud'])
@pytest.mark.parametrize('payload', [
    [], {'summary': []}, {**REPORT, 'rating': 'excellent'},
    {**REPORT, 'player_focus': {'topCreator': {'trackId': '<img src=x onerror=alert(1)>', 'team': 'my_team'}}},
    {**REPORT, 'evidence': [12]}, {**REPORT, 'rating': float('nan')},
])
def test_provider_output_is_validated(provider, payload, monkeypatch):
    response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
        'response': json.dumps(payload), 'choices': [{'message': {'content': json.dumps(payload)}}],
    })
    monkeypatch.setattr('requests.post', lambda *args, **kwargs: response)
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-only')
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs): return response
    monkeypatch.setattr('httpx.Client', Client)
    with pytest.raises(ValueError):
        llm._run_analysis_unguarded('tactical_report', [], provider=provider)


def test_legacy_provider_track_ids_are_escaped_in_html():
    attack = '<img src=x onerror="alert(1)">'
    html = render_match_report_html(
        match_name='Test', input_mode='video', exported_at='today', summary={},
        formation_timeline=[], event_summary={'topPlayers': [{'trackId': attack, 'team': 'my_team'}]},
        tactical_report={**REPORT, 'player_focus': {'topCreator': {'trackId': attack, 'team': 'my_team'}}}, drills=None,
    )
    assert attack not in html
    assert '&lt;img' in html


@pytest.mark.parametrize('analysis_type,payload', [
    ('tactical_report', REPORT),
    ('drills', {'drills': [{'name': 'Rondo', 'objective': 'Pass', 'setup': 'Circle', 'duration': '10m'}], 'focus_area': 'Possession'}),
])
def test_valid_provider_payloads_keep_the_public_shape(analysis_type, payload, monkeypatch):
    response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {'response': json.dumps(payload)})
    monkeypatch.setattr('requests.post', lambda *args, **kwargs: response)
    from backend.app.schemas import FrameData
    assert llm._run_analysis_unguarded(analysis_type, [FrameData(frameId=0, timestamp=0)], current_frame_index=0) == payload


def test_invalid_provider_result_does_not_replace_saved_report(api, monkeypatch):
    storage, client, _ = api
    match = make_match(storage)
    publish_minimal_generation(storage, match.id, [])
    storage.save_analysis_artifact(match.id, 'tactical_report', REPORT)
    invalid = {**REPORT, 'player_focus': {'topCreator': {'trackId': '<img src=x>', 'team': 'my_team'}}}
    response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {'response': json.dumps(invalid)})
    monkeypatch.setattr('requests.post', lambda *args, **kwargs: response)
    result = client.post(f'/api/matches/{match.id}/analysis/tactical_report', json={'provider': 'local'})
    assert result.status_code == 400
    assert storage.load_analysis_artifact(match.id, 'tactical_report') == REPORT


@pytest.mark.parametrize('fail_publication', [False, True])
def test_coach_reports_are_invalidated_only_after_successful_reprocessing(api, monkeypatch, fail_publication):
    storage, client, _ = api
    match = make_match(storage)
    publish_minimal_generation(storage, match.id, [])
    for name in ('tactical_report', 'drills'):
        storage.save_analysis_artifact(match.id, name, {'previous': True})
    if fail_publication:
        def fail(*args):
            raise OSError('config write failed')
        monkeypatch.setattr(storage.generations, '_commit_pointer', fail)
    result = client.patch(f'/api/matches/{match.id}/config', json={'attackDirection': 'right_to_left'})
    assert result.status_code == (500 if fail_publication else 200)
    for name in ('tactical_report', 'drills'):
        path = storage.storage_root / 'matches' / match.id / f'{name}.json'
        assert path.exists() == fail_publication
        if fail_publication:
            assert json.loads(path.read_text()) == {'previous': True}


@pytest.mark.parametrize('busy_status', ['match_processing', 'dispatching', 'queued', 'processing'])
def test_config_reprocessing_rejects_active_processing(api, monkeypatch, busy_status):
    storage, client, _ = api
    match = make_match(storage)
    if busy_status == 'match_processing':
        match = storage.update_match_status(match.id, status='processing')
    else:
        job = storage.create_job(match.id)
        storage.update_job(job.id, status=busy_status, progress=0)
    calls = []
    monkeypatch.setattr('backend.app.main.reprocess_video_match', lambda *args, **kwargs: calls.append(True))
    result = client.patch(f'/api/matches/{match.id}/config', json={'attackDirection': 'right_to_left'})
    assert result.status_code == 409
    assert storage.get_match(match.id) == match
    assert not calls


def test_concurrent_config_update_waits_for_failed_reprocess_rollback(api, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    storage, client, _ = api
    match = make_match(storage)
    publish_minimal_generation(storage, match.id, [])
    entered = threading.Event()
    release = threading.Event()
    second_started = threading.Event()

    def reprocess(*args, **kwargs):
        entered.set()
        assert release.wait(2)
        raise FileNotFoundError('missing late artifact')

    from backend.app.review_service import ReviewService
    monkeypatch.setattr(ReviewService, '_materialize', reprocess)

    def change_provider():
        second_started.set()
        return client.patch(f'/api/matches/{match.id}/config', json={'llmProvider': 'cloud'})

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(client.patch, f'/api/matches/{match.id}/config', json={'attackDirection': 'right_to_left'})
        try:
            assert entered.wait(1)
            second = pool.submit(change_provider)
            assert second_started.wait(1)
            assert not second.done()
            # The second mutation must not publish while rollback still owns the snapshot.
            from concurrent.futures import TimeoutError
            with pytest.raises(TimeoutError):
                second.result(timeout=0.15)
        finally:
            release.set()
        assert first.result(timeout=2).status_code == 409
        assert second.result(timeout=2).status_code == 200
    config = storage.get_match(match.id).config
    assert config.attackDirection == 'left_to_right'
    assert config.llmProvider == 'cloud'


def test_late_analysis_cannot_republish_after_config_change(api, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    storage, client, _ = api
    match = make_match(storage, 'tracking_json')
    publish_minimal_generation(storage, match.id, [FrameData(frameId=0,timestamp=0)])
    started, release = threading.Event(), threading.Event()
    def slow_analysis(*args, **kwargs):
        started.set()
        assert release.wait(5)
        return {'summary':'stale'}
    monkeypatch.setattr('backend.app.main.run_analysis', slow_analysis)
    with ThreadPoolExecutor() as pool:
        request = pool.submit(client.post, f'/api/matches/{match.id}/analysis/tactical_report', json={})
        try:
            assert started.wait(5)
            assert client.patch(f'/api/matches/{match.id}/config',json={'attackDirection':'right_to_left'}).status_code==200
        finally:
            release.set()
        assert request.result().status_code==409
    assert not (storage.storage_root/'matches'/match.id/'tactical_report.json').exists()


@pytest.mark.parametrize('analysis_type', ['offside', 'spacing'])
def test_provider_cannot_generate_geometry(analysis_type):
    from backend.app.schemas import FrameData
    with pytest.raises(ValueError, match='Unsupported analysis type'):
        llm.build_prompt(analysis_type, [FrameData(frameId=0, timestamp=0)])
