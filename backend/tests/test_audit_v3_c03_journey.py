"""C03's report/state portion of V3T50; real processes, synthetic observations.

This is not C04-C06 acceptance, a browser test or learned-model evaluation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from backend.app.storage import Storage
from backend.tests.test_audit_v3_c01_generations import _child_setup, children as children
from backend.tests.test_audit_v3_c03_publication import _export_reader

pytestmark = pytest.mark.integration


def _crashing_configuration(root, mid, pipe):
    _child_setup()
    try:
        storage = Storage(Path(root))
        from backend.app.review_service import ReviewService

        def barrier(point):
            if point == 'after_pointer_publish':
                pipe.send(('committed', point))
                pipe.recv()  # Parent kills the real child before SQL/receipt updates.

        storage._review_test_fault = barrier
        ReviewService(storage).configure(mid, {
            'attackDirection': 'right_to_left', 'commandId': 'c03-crash-command',
            'baseGeneration': storage.current_generation(mid).generationId,
        })
    finally:
        pipe.close()


@pytest.mark.parametrize('mode', ['video', 'tracking_json'])
def test_report_and_accepted_state_survive_composed_edits_crash_and_old_reader(tmp_path, monkeypatch, children, mode):
    # Import perception-adjacent helpers only after the child import guard runs.
    import backend.app.processor as processor
    from backend.app.accepted_state import validate_state
    from backend.app.main import create_app
    from backend.app.report_store import ReportStore
    from backend.tests.test_audit_v3_c02_identity import tracking
    from backend.tests.test_audit_v3_c02_projection import profile, video
    from backend.tests.test_audit_v3_c03_reports import _gateway, _interprets
    from fastapi.testclient import TestClient

    monkeypatch.setattr(processor, 'process_video_input', lambda *a, **kw: pytest.fail('Unexpected inference'))
    storage = Storage(tmp_path / 'store')
    if mode == 'video':
        mid = video(storage, tmp_path)
        storage.commit_calibration_for_match(mid, profile().model_dump(mode='json'))
    else:
        mid = tracking(storage, tmp_path)
    storage.promote_identity_for_match(mid, {'reviewed': True})
    sources = [storage.get_match_input_path(mid)]
    if mode == 'video':
        sources.append(storage.generations.root(mid) / 'raw_rows.json')
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    calls = []

    def adapter(*args, **kwargs):
        calls.append(kwargs['approved_evidence']['generationId'])
        return _interprets(*args, **kwargs)

    old = storage.current_generation(mid).generationId
    _gateway(storage, adapter).execute(mid, 'tactical_report')
    reader = children(_export_reader, str(storage.storage_root), mid)
    assert reader.receive() == ('pinned', old)
    storage.commit_calibration_for_match(mid, profile(dx=5.).model_dump(mode='json'))
    split = storage.submit_correction(mid, kind='track_split', payload={'trackId': '7', 'atFrame': 2, 'newTrackId': 99})
    assert storage.identity_eligibility(mid)['continuous'] is False
    storage.undo_correction(mid, split.correctionId)
    storage.promote_identity_for_match(mid, {'reviewed': True})
    assert ReportStore(storage).view(mid)['reports'] == {}

    writer = children(_crashing_configuration, str(storage.storage_root), mid)
    assert writer.receive() == ('committed', 'after_pointer_publish')
    committed = json.loads((storage.generations.root(mid) / 'current_generation.json').read_text())['generationId']
    writer.process.kill()
    writer.process.join(10)
    assert not writer.process.is_alive() and writer.process.exitcode != 0
    reopened = Storage(storage.storage_root)
    assert reopened.current_generation(mid).generationId == committed != old
    assert reopened.get_match(mid).config.attackDirection == 'right_to_left'
    command = next(c for c in reopened.list_corrections(mid) if c['commandId'] == 'c03-crash-command')
    assert command['applyState'] == 'applied' and command['appliedGeneration'] == committed
    for _ in range(2):
        reopened.recover_correction(mid, command['correctionId'])
        assert reopened.current_generation(mid).generationId == committed
    assert calls == [old], 'Recovery must not dispatch another report request'
    new_report = _gateway(reopened, adapter).execute(mid, 'tactical_report')
    assert calls == [old, committed]
    with TestClient(create_app(storage_root=reopened.storage_root), base_url='http://127.0.0.1') as client:
        bundle = client.get(f'/api/matches/{mid}/export/match.json').json()
        assert bundle['generationId'] == committed
        validate_state(bundle['acceptedMatchState'], mid, committed, bundle['frames'], bundle['analytics']['ballAssignments'])
        assert bundle['acceptedMatchState']['availability'] == 'available'
        assert bundle['reports']['reports']['tactical_report']['reportId'] == new_report['reportId']
        assert bundle['reports']['reports']['tactical_report']['generationId'] == committed
        assert client.get(f'/api/matches/{mid}/export/metrics.csv').headers['x-generation-id'] == committed
        assert client.get(f'/api/matches/{mid}/report/html').headers['x-generation-id'] == committed
    reader.pipe.send('read')
    historical = reader.receive()
    reader.finish()
    assert {historical[k] for k in ('generationId', 'stateGeneration', 'playlistGeneration', 'reportGeneration')} == {old}
    assert historical['direction'] == 'left_to_right'
    assert 'INTERPRETIVE_SENTINEL' in historical['html']
    assert ReportStore(reopened).view(mid, generation_id=old)['status'] == 'historical'
    assert {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources} == before
