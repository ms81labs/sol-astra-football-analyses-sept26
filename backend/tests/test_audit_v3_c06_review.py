"""C06 independent failure-mode pass; synthetic fixtures, no model inference."""
from __future__ import annotations
import json
import time
from pathlib import Path

import pytest
from backend.app.workbench import media
from backend.app.workbench.contracts import SourceClockIdentity
from backend.app.workbench.media_execution import MediaExecutionPolicy
from backend.tests.test_audit_v3_c06_media import clip, controlled_decoder


def test_resident_budget_accounts_for_frame_assembly_and_bytes_conversion():
    identity=SourceClockIdentity(sourceSha256='a'*64,byteSize=1,width=2,height=2)
    with pytest.raises(media.MediaResourceLimit,match='buffer'):
        MediaExecutionPolicy(max_buffer_bytes=12).decode_budget(identity)


@pytest.mark.real_media
def test_truncated_successful_child_is_not_a_completed_decode_receipt(tmp_path):
    path,adapter=controlled_decoder(tmp_path,'import sys\nsys.stdout.buffer.write(b"x")\n',MediaExecutionPolicy())
    with pytest.raises(media.TruncatedStream):
        list(adapter.iter_frames(path))
    assert adapter.last_execution_receipt['outcome']=='TRUNCATED_STREAM'
    assert adapter.last_execution_receipt['reaped']


@pytest.mark.real_media
def test_probe_refusal_is_not_a_success_receipt(tmp_path):
    path=clip(tmp_path/'too-long.mp4',duration=2)
    probe=media.FfmpegProbe(policy=MediaExecutionPolicy(max_duration_seconds=1))
    with pytest.raises(media.MediaResourceLimit,match='SOURCE_NOT_ADMITTED'):
        probe.probe_identity(path)
    assert probe.last_execution_receipt['outcome']=='SOURCE_NOT_ADMITTED'
    assert probe.last_execution_receipt['reaped']


@pytest.mark.real_media
def test_changed_source_during_probe_cannot_bind_new_bytes_to_old_metadata(tmp_path,monkeypatch):
    path=clip(tmp_path/'changed.mp4')
    bounded=media._run_bounded_media_process
    def race(*args,**kwargs):
        result=bounded(*args,**kwargs)
        with path.open('ab') as output: output.write(b'changed')
        return result
    monkeypatch.setattr(media,'_run_bounded_media_process',race)
    with pytest.raises(ValueError,match='source changed'):
        media.FfmpegProbe().probe_identity(path)


@pytest.mark.real_media
def test_whole_export_deadline_is_shared_across_source_probe_and_transform(tmp_path,monkeypatch):
    path=clip(tmp_path/'source.mp4')
    output=tmp_path/'output.mp4'; output.write_bytes(b'previous')
    bounded=media._run_bounded_media_process
    def slow_boundary(*args,**kwargs):
        time.sleep(.2)
        return bounded(*args,**kwargs)
    monkeypatch.setattr(media,'_run_bounded_media_process',slow_boundary)
    with pytest.raises(media.MediaResourceLimit,match='wall-clock'):
        media.FfmpegProbe(policy=MediaExecutionPolicy(job_timeout_seconds=.35)).export_clip(
            path,output,start_seconds=0,duration_seconds=.5)
    assert output.read_bytes()==b'previous'
    assert not list(tmp_path.glob('.ga-media-*'))


@pytest.mark.real_media
def test_tiny_frames_use_timing_backpressure_not_spurious_buffer_failure(tmp_path):
    path,adapter=controlled_decoder(tmp_path,
        'import sys\nfor i in range(200):\n'
        ' sys.stderr.write(f"n:{i} pts:{i} pts_time:{i/25}\\n");sys.stderr.flush()\n'
        ' sys.stdout.buffer.write(b"x"*12);sys.stdout.flush()\n',MediaExecutionPolicy())
    iterator=adapter.iter_frames(path)
    first=next(iterator)
    time.sleep(.2)
    remaining=list(iterator)
    assert len(remaining)+1==200
    assert first.pts==0 and remaining[-1].pts==199
    assert adapter.last_execution_receipt['peakTimingEntries']<=64


def test_storage_reports_media_refusal_without_fallback_success(tmp_path,monkeypatch):
    from backend.app.storage import Storage
    from backend.app.schemas import MatchConfig
    path=tmp_path/'source.mp4';path.write_bytes(b'synthetic')
    storage=Storage(tmp_path/'store')
    match=storage.create_match(name='policy refusal',input_mode='video',original_filename=path.name,
                               input_path=path,config=MatchConfig())
    def refuse(*args,**kwargs):
        raise media.MediaResourceLimit('MODE_NOT_QUALIFIED: offline_match')
    monkeypatch.setattr(media,'run_proxy_ffmpeg_job',refuse)
    try:
        receipt=storage.proxy_assets_for_match(match.id)
        assert receipt['ranFfmpeg'] is False
        assert receipt['mediaExecution']['outcome']=='MODE_NOT_QUALIFIED'
        assert receipt['mediaExecution']['published'] is False
        assert receipt['mediaExecution']['fallback']=='not_attempted'
    finally:
        storage.close()


@pytest.mark.real_media
def test_explicit_byte_cap_reads_only_one_sentinel_byte_beyond_limit(tmp_path,monkeypatch):
    path=clip(tmp_path/'cap.mp4')
    read=media._read_exact
    seen=[]
    def count(*args,**kwargs):
        data=read(*args,**kwargs)
        seen.append(len(data) if data is not None else 0)
        return data
    monkeypatch.setattr(media,'_read_exact',count)
    limit=32*24*3+1
    with pytest.raises(media.MediaResourceLimit,match='output-byte cap'):
        list(media.FfmpegFrameSource(max_output_bytes=limit).iter_frames(path))
    assert sum(seen)<=limit+1


@pytest.mark.parametrize("video, expected", [
    ({"tags": {"rotate": "-90"}}, -90),
    ({"tags": {"rotate": "0"}, "side_data_list": [{"rotation": 90}]}, 90),
    ({"side_data_list": [{"rotation": -90}]}, -90),
    ({"side_data_list": [{"side_data_type": "other"}]}, 0),
])
def test_rotation_metadata_precedence_and_legacy_controls(video, expected):
    assert media._rotation_from_tags(video) == expected


@pytest.mark.parametrize("rotation", ["NaN", "Infinity", 90.5, True])
def test_unrepresentable_display_rotation_is_refused(rotation):
    with pytest.raises(media.MediaResourceLimit, match="SOURCE_NOT_ADMITTED"):
        media._rotation_from_tags({"side_data_list": [{"rotation": rotation}]})
