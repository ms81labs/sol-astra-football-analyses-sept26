"""Actual generated media and process lifecycles for V3T45–49."""
from __future__ import annotations
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from backend.app.workbench import media
from backend.app.workbench.media_execution import MediaExecutionPolicy
from backend.app.workbench.contracts import SourceClockIdentity


def clip(path, *, duration=1, rate=4, size='32x24'):
    subprocess.run([str(media.resolve_trusted_executable('ffmpeg')), '-hide_banner',
        '-loglevel', 'error', '-f', 'lavfi', '-i', f'color=black:size={size}:rate={rate}:duration={duration}',
        '-threads','1','-pix_fmt','yuv420p','-y',str(path)],check=True,timeout=40)
    return path


def controlled_decoder(tmp_path, code, p):
    executable=tmp_path/'ffmpeg'
    executable.write_text(f'#!{sys.executable} -S\n'+code)
    executable.chmod(0o755)
    settings=SimpleNamespace(trusted_bin_dirs=(str(tmp_path),),ffmpeg_sha256=None,ffprobe_sha256=None)
    source=tmp_path/'source.mp4'; source.write_bytes(b'fixture')
    probe=media.FfmpegProbe(ffmpeg=str(executable),settings=settings,policy=p)
    identity=SourceClockIdentity(sourceSha256='a'*64,byteSize=7,width=2,height=2,timeBaseNum=1,timeBaseDen=25)
    return source, media.FfmpegFrameSource(identity=identity,probe=probe,policy=p)


@pytest.mark.real_media
def test_slow_consumer_is_not_decoder_stall(tmp_path):
    source=clip(tmp_path/'small.mp4')
    adapter=media.FfmpegFrameSource(policy=MediaExecutionPolicy(stall_timeout_seconds=.15,job_timeout_seconds=5))
    count=0
    for frame in adapter.iter_frames(source):
        assert frame.width==32
        time.sleep(.25)
        count+=1
    assert count==4
    assert adapter.last_execution_receipt['outcome']=='completed'
    assert adapter.last_execution_receipt['reaped']


@pytest.mark.real_media
def test_active_stall_and_paused_job_deadline_reap_without_generator_resume(tmp_path):
    p=MediaExecutionPolicy(stall_timeout_seconds=.15,job_timeout_seconds=4)
    source,adapter=controlled_decoder(tmp_path,
        'import sys,time\nsys.stdout.buffer.write(b"x"*12);sys.stdout.flush()\n'
        'sys.stderr.write("n:0 pts:0 pts_time:0.0\\n");sys.stderr.flush()\ntime.sleep(30)\n',p)
    iterator=adapter.iter_frames(source)
    assert len(next(iterator).payload)==12
    with pytest.raises(media.MediaResourceLimit, match='stalled'):
        next(iterator)
    assert adapter.last_execution_receipt['outcome']=='DECODER_STALL'
    assert adapter.last_execution_receipt['reaped']

    p=replace(p,job_timeout_seconds=.45)
    source,adapter=controlled_decoder(tmp_path,
        'import sys,time\nsys.stdout.buffer.write(b"x"*12);sys.stdout.flush()\n'
        'sys.stderr.write("n:0 pts:0 pts_time:0.0\\n");sys.stderr.flush()\ntime.sleep(30)\n',p)
    iterator=adapter.iter_frames(source); next(iterator)
    deadline=time.monotonic()+3
    while not adapter.last_execution_receipt['reaped'] and time.monotonic()<deadline:
        time.sleep(.02)
    assert adapter.last_execution_receipt['reaped'], 'watchdog must reap while consumer is paused'
    with pytest.raises(media.MediaResourceLimit, match='wall-clock'):
        next(iterator)


@pytest.mark.real_media
def test_blocked_decode_cancel_and_early_close_reap(tmp_path):
    p=MediaExecutionPolicy(stall_timeout_seconds=3,job_timeout_seconds=5)
    source,adapter=controlled_decoder(tmp_path,'import time\ntime.sleep(30)\n',p)
    cancel=threading.Event(); timer=threading.Timer(.2,cancel.set); timer.start()
    try:
        with pytest.raises(media.DecodeCancelled):
            list(adapter.iter_frames(source,cancel_event=cancel))
    finally: timer.cancel()
    assert adapter.last_execution_receipt['reaped']
    source,adapter=controlled_decoder(tmp_path,
        'import sys,time\nsys.stdout.buffer.write(b"x"*12);sys.stdout.flush()\n'
        'sys.stderr.write("n:0 pts:0 pts_time:0.0\\n");sys.stderr.flush()\ntime.sleep(30)\n',p)
    iterator=adapter.iter_frames(source); next(iterator); iterator.close()
    assert adapter.last_execution_receipt['reaped']
    assert adapter.last_execution_receipt['outcome']=='GENERATOR_CLOSED'


@pytest.mark.real_media
def test_generated_long_duration_uses_bounded_buffer_and_preserves_strict_work_cap(tmp_path):
    source=clip(tmp_path/'long.mp4',duration=70,rate=4)
    adapter=media.FfmpegFrameSource(policy=MediaExecutionPolicy(max_buffer_bytes=2*32*24*3))
    assert sum(1 for _ in adapter.iter_frames(source))==280
    receipt=adapter.last_execution_receipt
    assert receipt['decodedBytes']==280*32*24*3
    assert receipt['peakReadBufferBytes']==2*32*24*3
    assert receipt['queuedFrames']==0
    capped=media.FfmpegFrameSource(max_output_bytes=32*24*3*2+1)
    with pytest.raises(media.MediaResourceLimit,match='output-byte cap'):
        list(capped.iter_frames(source))
    assert capped.last_execution_receipt['reaped']


@pytest.mark.real_media
def test_actual_proxy_export_file_limit_retains_source_and_existing_output(tmp_path):
    source=clip(tmp_path/'source with spaces.mp4')
    before=source.read_bytes()
    destination=tmp_path/'output with spaces.mp4'; destination.write_bytes(b'old artifact')
    p=MediaExecutionPolicy(max_file_bytes=128)
    with pytest.raises((media.DecoderFailed,media.MediaResourceLimit)):
        media.run_proxy_ffmpeg_job(source,destination,original_sha256=hashlib.sha256(before).hexdigest(),proxy_height=24,policy=p)
    assert destination.read_bytes()==b'old artifact'
    assert source.read_bytes()==before
    assert not list(tmp_path.glob('.ga-media-*'))
    exporter=media.FfmpegProbe()
    exporter.export_clip(source,destination,start_seconds=0,duration_seconds=.5)
    assert exporter.last_execution_receipt['enforcedLimits']
    assert exporter.last_execution_receipt['reaped']
    assert source.read_bytes()==before


@pytest.mark.real_media
def test_proxy_refuses_nonadmitted_duration_instead_of_silently_truncating(tmp_path):
    source=clip(tmp_path/'longer-than-mode.mp4',duration=2)
    with pytest.raises(media.MediaResourceLimit,match='SOURCE_NOT_ADMITTED'):
        media.run_proxy_ffmpeg_job(source,tmp_path/'out.mp4',
            original_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),proxy_height=24,
            policy=MediaExecutionPolicy(max_duration_seconds=1))
    assert not (tmp_path/'out.mp4').exists()


def test_explicit_policy_overrides_supplied_probe_without_mutating_it():
    probe=media.FfmpegProbe()
    p=MediaExecutionPolicy(cpu_soft_seconds=3,cpu_hard_seconds=5,threads=1)
    source=media.FfmpegFrameSource(probe=probe,policy=p)
    assert source._probe.policy==p
    assert probe.policy!=p


@pytest.mark.real_media
def test_rotation_preserves_source_pixel_dimensions_and_integer_pts(tmp_path):
    source=clip(tmp_path/'source.mp4')
    rotated=tmp_path/'rotated.mp4'
    subprocess.run([str(media.resolve_trusted_executable('ffmpeg')),'-loglevel','error','-display_rotation','90','-i',str(source),
                    '-c','copy','-y',str(rotated)],check=True,timeout=15)
    adapter=media.FfmpegFrameSource()
    raw = json.loads(subprocess.run([str(media.resolve_trusted_executable('ffprobe')),
        '-v','error','-show_streams','-of','json',str(rotated)],
        check=True,capture_output=True,text=True,timeout=10).stdout)
    assert any(item.get('rotation')==90 for item in raw['streams'][0].get('side_data_list',[]))
    identity=adapter.probe(rotated)
    frames=list(adapter.iter_frames(rotated))
    assert len(frames)==4
    assert identity.rotation == 90
    assert all((f.width,f.height)==(32,24) for f in frames)
    assert all(f.rotation==identity.rotation and f.pts is not None for f in frames)


@pytest.mark.real_media
@pytest.mark.skipif(os.environ.get('C06_LONG_MEDIA')!='1',reason='opt-in >8 GiB synthetic decode; not football performance qualification')
def test_optin_beyond_old_eight_gib_total(tmp_path):
    source=clip(tmp_path/'hd-minute.mp4',duration=60,rate=25,size='1920x1080')
    adapter=media.FfmpegFrameSource()
    count=sum(1 for _ in adapter.iter_frames(source))
    receipt=adapter.last_execution_receipt
    assert count==1500
    assert receipt['decodedBytes']>8*1024**3
    assert receipt['peakReadBufferBytes']<=adapter.policy.max_buffer_bytes
    output=os.environ.get('C06_LONG_RECEIPT')
    if output:
        Path(output).write_text(json.dumps(receipt,indent=2))


@pytest.mark.real_media
def test_relative_paths_survive_scratch_cwd_without_overwriting_source(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    source=clip(Path('source with spaces.mp4'))
    before=source.read_bytes()
    exporter=media.FfmpegProbe()
    exporter.export_clip(source,Path('clip with spaces.mp4'),start_seconds=0,duration_seconds=.5)
    result=media.run_proxy_ffmpeg_job(source,Path('proxy with spaces.mp4'),
        original_sha256=hashlib.sha256(before).hexdigest(),proxy_height=24)
    assert Path('clip with spaces.mp4').stat().st_size>0
    assert Path('proxy with spaces.mp4').stat().st_size>0
    assert result['mediaExecution']['published']
    assert not result['assets']['proxy']['streamCopy']
    assert source.read_bytes()==before
