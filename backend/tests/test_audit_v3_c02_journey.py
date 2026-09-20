"""C02 portion of V3T50: composed edits with a separate pinned reader.

Synthetic post-perception fixtures only. Full report/money/cache/media acceptance
belongs to C03-C06; this test does not claim that larger journey or ML accuracy.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.semantic_commands import SemanticCommandError
from backend.app.storage import Storage
from backend.tests.test_audit_v3_c01_generations import _child_setup, children as children

pytestmark = pytest.mark.integration


def _snapshot(storage, mid):
    frames = storage.load_frames(mid)
    return {
        'generation': storage.current_generation(mid).generationId,
        'coordinates': [(f.frameId, [(p.id, p.x, p.y) for p in f.myTeam]) for f in frames],
        'direction': storage.get_match(mid).config.attackDirection,
        'identity': storage.identity_eligibility(mid),
        'distance': storage.derived_distance_for_match(mid),
    }


def _held_reader(root, mid, pipe):
    _child_setup()
    try:
        storage = Storage(Path(root))
        with storage.generation_snapshot(mid) as ref:
            first = _snapshot(storage, mid)
            pipe.send(('pinned', ref.generationId))
            assert pipe.recv() == 'read'
            pipe.send((first, _snapshot(storage, mid)))
    except BaseException as error:
        pipe.send(('error', repr(error)))
        raise
    finally:
        pipe.close()


@pytest.mark.parametrize('mode', ['video', 'tracking_json'])
def test_c02_composed_journey_preserves_old_reader_and_replays_once(tmp_path, monkeypatch, children, mode):
    import backend.app.processor as processor
    from backend.tests.test_audit_v3_c02_identity import tracking
    from backend.tests.test_audit_v3_c02_projection import profile, video

    monkeypatch.setattr(processor, 'process_video_input', lambda *a, **k: pytest.fail('Unapproved perception invocation'))
    app = create_app(storage_root=tmp_path / 'store')
    storage = app.state.storage
    if mode == 'video':
        mid = video(storage, tmp_path)
        storage.commit_calibration_for_match(mid, profile().model_dump(mode='json'))
    else:
        mid = tracking(storage, tmp_path)
    storage.promote_identity_for_match(mid, {'reviewed': True})
    initial = _snapshot(storage, mid)
    source = storage.generations.root(mid) / 'raw_rows.json' if mode == 'video' else storage.get_match_input_path(mid)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    reader = children(_held_reader, str(storage.storage_root), mid)
    assert reader.receive() == ('pinned', initial['generation'])
    base = {'baseGeneration': initial['generation'], 'commandId': 'journey-direction', 'attackDirection': 'right_to_left'}
    with TestClient(app, base_url='http://127.0.0.1') as client:
        first = client.patch(f'/api/matches/{mid}/config', json=base)
        assert first.status_code == 200, first.text
        receipt = first.json()['correction']
        assert receipt['applyState'] == 'applied'
        storage.commit_calibration_for_match(mid, profile(dx=5.).model_dump(mode='json'))
        split = storage.submit_correction(mid, kind='track_split', payload={'trackId': '7', 'atFrame': 2, 'newTrackId': 99})
        assert storage.identity_eligibility(mid)['continuous'] is False
        assert storage.derived_distance_for_match(mid)['availability'] == 'withheld'
        joined = storage.submit_correction(mid, kind='track_join', payload={'leftTrackId': '7', 'rightTrackId': '99'})
        before_conflict = (storage.current_generation(mid).generationId, storage.list_corrections(mid))
        with pytest.raises(SemanticCommandError, match='dependent') as error:
            storage.undo_correction(mid, split.correctionId)
        assert error.value.code == 'COMMAND_DEPENDENCY_CONFLICT'
        assert (storage.current_generation(mid).generationId, storage.list_corrections(mid)) == before_conflict
        storage.undo_correction(mid, joined.correctionId)
        storage.undo_correction(mid, split.correctionId)
        assert storage.identity_eligibility(mid)['continuous'] is False
        approval = storage.promote_identity_for_match(mid, {'reviewed': True})['correction']
        final = _snapshot(storage, mid)
        assert final['identity']['continuous'] is True
        assert final['direction'] == 'right_to_left'
        assert final['coordinates'][0][1][0][1:] == pytest.approx((17., 30.) if mode == 'video' else (12., 30.))
        assert final['distance']['value'] == pytest.approx(initial['distance']['value'])
        repeated = client.patch(f'/api/matches/{mid}/config', json=base)
        assert repeated.status_code == 200, repeated.text
        assert repeated.json()['correction'] == receipt
        assert _snapshot(storage, mid) == final  # A historical receipt is not a current-state rollback.
        stale = client.patch(f'/api/matches/{mid}/config', json={**base, 'commandId': 'stale-new-command'})
        assert stale.status_code == 409
        assert _snapshot(storage, mid) == final
    reader.pipe.send('read')
    old_first, old_last = reader.receive()
    reader.finish()
    assert old_first == old_last == initial
    reopened = Storage(storage.storage_root)
    for _ in range(2):
        reopened.recover_correction(mid, approval['correctionId'])
        assert _snapshot(reopened, mid) == final
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
