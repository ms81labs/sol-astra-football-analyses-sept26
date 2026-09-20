"""C02 N06 counters wrap actual stages; no detector/remote work is performed."""
from __future__ import annotations
from pathlib import Path
import pytest
import backend.app.processor as processor
import backend.app.review_service as review_service
from backend.app.processor import process_match, reprocess_video_match
from backend.app.schemas import MatchConfig
from backend.app.storage import Storage
from backend.tests.test_audit_v2_h02_review import install_raw_row_match, install_tracking_match

pytestmark = pytest.mark.integration


def stage_counter(monkeypatch):
    counts = {'materialisations': 0, 'summaries': 0, 'detectors': 0}
    stage, summary = processor._compute_outputs_and_match_state, processor.summarize_match
    def counted_stage(*args, **kwargs):
        counts['materialisations'] += 1
        return stage(*args, **kwargs)
    def counted_summary(*args, **kwargs):
        counts['summaries'] += 1
        return summary(*args, **kwargs)
    def no_detector(*args, **kwargs):
        counts['detectors'] += 1
        pytest.fail('Post-perception edit invoked detector')
    monkeypatch.setattr(processor, '_compute_outputs_and_match_state', counted_stage)
    monkeypatch.setattr(review_service, '_compute_outputs_and_match_state', counted_stage, raising=False)
    monkeypatch.setattr(processor, 'summarize_match', counted_summary)
    monkeypatch.setattr(review_service, 'summarize_match', counted_summary, raising=False)
    monkeypatch.setattr(processor, 'process_video_input', no_detector)
    return counts


@pytest.mark.parametrize('mode', ['video', 'tracking_json'])
def test_v3t20_corrected_reprocessing_has_one_full_materialisation(tmp_path, monkeypatch, mode):
    storage = Storage(tmp_path / 'store')
    mid = install_raw_row_match(storage, tmp_path) if mode == 'video' else install_tracking_match(storage)
    storage.submit_correction(mid, kind='team_mapping', payload={'swap': True})
    counts = stage_counter(monkeypatch)
    if mode == 'video':
        reprocess_video_match(storage, mid)
    else:
        process_match(storage, storage.create_job(mid).id)
    assert counts == {'materialisations': 1, 'summaries': 1, 'detectors': 0}
    assert storage.load_frames(mid)[0].enemies[0].id == 7


def test_v3t20_initial_processing_uses_canonical_stage_once(tmp_path, monkeypatch):
    storage = Storage(tmp_path / 'store')
    fixture = Path(__file__).parent / 'fixtures' / 'sample_tracking.json'
    match = storage.create_match('New tracking', 'tracking_json', fixture.name, fixture, MatchConfig())
    counts = stage_counter(monkeypatch)
    process_match(storage, storage.create_job(match.id).id)
    assert counts == {'materialisations': 1, 'summaries': 1, 'detectors': 0}


def test_v3t20_duplicate_delivery_and_completed_recovery_do_no_materialisation(tmp_path, monkeypatch):
    storage = Storage(tmp_path / 'store');mid = install_tracking_match(storage)
    counts = stage_counter(monkeypatch)
    receipt = storage.submit_correction(mid, kind='team_mapping', payload={'swap': True},command_id='once')
    assert counts['materialisations'] == counts['summaries'] == 1
    before = storage.current_generation(mid).generationId
    again = storage.submit_correction(mid, kind='team_mapping', payload={'swap': True},command_id='once')
    storage.recover_correction(mid, receipt.correctionId)
    assert again.appliedGeneration == receipt.appliedGeneration == before
    assert counts == {'materialisations': 1, 'summaries': 1, 'detectors': 0}


def test_v3t20_failed_attempt_recovery_does_exactly_one_new_attempt(tmp_path, monkeypatch):
    storage = Storage(tmp_path / 'store');mid = install_tracking_match(storage)
    counts = stage_counter(monkeypatch)
    original = processor.detect_events
    monkeypatch.setattr(processor, 'detect_events', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('test interruption')))
    before = storage.current_generation(mid).generationId
    with pytest.raises(Exception):
        storage.submit_correction(mid,kind='team_mapping',payload={'swap': True},command_id='retry')
    assert storage.current_generation(mid).generationId == before
    assert counts == {'materialisations': 1, 'summaries': 0, 'detectors': 0}
    monkeypatch.setattr(processor, 'detect_events', original)
    failed = next(item for item in storage.list_corrections(mid) if item["commandId"] == "retry")
    receipt = storage.recover_correction(mid, failed["correctionId"])
    assert receipt.applyState == 'applied'
    assert counts == {'materialisations': 2, 'summaries': 1, 'detectors': 0}


@pytest.mark.parametrize('streaming', [False, True])
def test_initial_video_post_perception_handoff_does_one_materialisation(tmp_path, monkeypatch, streaming):
    """Local import paths use synthetic observations, never a remote worker."""
    from backend.app.remote_worker import ProcessorResultStream
    s = Storage(tmp_path / 'store')
    source = tmp_path / 'source.mp4'
    source.write_bytes(b'Synthetic post-perception source identity; not decoded')
    m = s.create_match('New video', 'video', source.name, source, MatchConfig(myTeamCluster=0))
    job = s.create_job(m.id)
    rows = [
        {'Frame_ID': frame, 'Timestamp': frame / 5, 'Entity_Type': 'player',
         'Track_ID': track, 'X': x + frame, 'Y': 30., 'Conf': .9}
        for frame in range(3) for track, x in [(7, 12.), (18, 80.)]
    ]
    metadata = {'trackColors': {'7': [[220, 20, 20]], '18': [[20, 20, 220]]}}
    counts = stage_counter(monkeypatch)
    # The trusted initial parser result is reused; the canonical stage must not
    # load and duplicate the full raw-row file immediately after writing it.
    monkeypatch.setattr(s, 'load_raw_rows', lambda *_: pytest.fail('Duplicate full raw-row load'))
    if streaming:
        with s.remote_result_import(m.id), ProcessorResultStream(metadata, len(rows), iter(rows)) as stream:
            processor.persist_remote_video_result_stream(s, job.id, stream)
    else:
        processor._persist_video_outputs(s, job.id, m.id, m.config, {**metadata, 'rows': rows},
                                        processing_backend='local', video_path=source, worker_path='local')
    assert counts == {'materialisations': 1, 'summaries': 1, 'detectors': 0}
    assert s.current_generation(m.id).generationId
    assert s.load_frames(m.id)[0].myTeam[0].id == 7
