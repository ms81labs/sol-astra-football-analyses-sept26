"""C06 acceptance extensions: real limits, not a mocked success receipt."""
from __future__ import annotations
import json
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from backend.app.workbench import media


def policy(**kwargs):
    from backend.app.workbench.media_execution import MediaExecutionPolicy
    return MediaExecutionPolicy(**kwargs)


def run(code, *, p=None, **kwargs):
    return media._run_bounded_media_process(
        [sys.executable, '-I', '-S', '-c', code], timeout=10,
        output_cap=65536, file_cap=1 << 20, policy=p or policy(), **kwargs)


def test_policy_digest_is_stable_and_modes_fail_closed(tmp_path):
    p = policy()
    assert p.digest == policy().digest
    assert p.digest != policy(cpu_soft_seconds=5, cpu_hard_seconds=7).digest
    for mode in ('offline_match', 'live'):
        with pytest.raises(media.MediaResourceLimit, match='MODE_NOT_QUALIFIED'):
            list(media.FfmpegFrameSource(policy=policy(mode=mode)).iter_frames(tmp_path/'unused.mp4'))


@pytest.mark.parametrize('field,value', [
    ('threads', True), ('threads', 0), ('job_timeout_seconds', float('nan')),
    ('stall_timeout_seconds', -1), ('max_frames', 0), ('max_width', 1 << 64),
    ('max_decoded_bytes', 0), ('max_buffer_bytes', -1),
])
def test_policy_rejects_unbounded_or_invalid_values(field, value):
    with pytest.raises(ValueError):
        policy(**{field: value})


@pytest.mark.integration
def test_configured_kernel_limits_reach_actual_child():
    p=policy(cpu_soft_seconds=4, cpu_hard_seconds=6, address_space_bytes=128 << 20)
    result=run('import resource,json;print(json.dumps({n:resource.getrlimit(getattr(resource,n)) for n in ("RLIMIT_CPU","RLIMIT_AS","RLIMIT_FSIZE")}))', p=p)
    actual=json.loads(result.stdout)
    assert actual == {'RLIMIT_CPU':[4,6], 'RLIMIT_AS':[128 << 20]*2, 'RLIMIT_FSIZE':[1 << 20]*2}
    receipt=result.execution_receipt
    assert receipt['enforcedLimits'] == actual
    assert receipt['reaped'] is True
    assert receipt['outcome'] == 'completed'
    assert receipt['policySha256']
    assert receipt['filesystemIsolation'] is False


@pytest.mark.integration
def test_small_cpu_limit_and_unrelated_sigkill_are_not_conflated():
    with pytest.raises(media.DecoderFailed) as cpu:
        run('while True: pass', p=policy(cpu_soft_seconds=1,cpu_hard_seconds=2))
    assert cpu.value.code in (-signal.SIGXCPU, -signal.SIGKILL)
    assert cpu.value.execution_receipt['reaped']
    with pytest.raises(media.DecoderFailed) as other:
        run('import os,signal;os.kill(os.getpid(),signal.SIGKILL)')
    assert other.value.code == -signal.SIGKILL
    assert other.value.execution_receipt['outcome'] == 'CHILD_SIGNAL_UNKNOWN'


@pytest.mark.integration
def test_address_space_limit_is_observed_not_labelled_rss():
    result=run('try:\n x=bytearray(128*1024*1024)\nexcept MemoryError:\n print("bounded")',
               p=policy(address_space_bytes=32 << 20))
    assert result.stdout.strip() == b'bounded'
    assert result.execution_receipt['enforcedLimits']['RLIMIT_AS'] == [32 << 20]*2


@pytest.mark.integration
def test_file_size_limit_caps_a_real_regular_file(tmp_path):
    output=tmp_path/'large.bin'
    with pytest.raises(media.DecoderFailed) as failure:
        run(f'open({str(output)!r},"wb").write(b"x"*(2*1024*1024))')
    assert output.stat().st_size <= 1 << 20
    assert failure.value.execution_receipt['enforcedLimits']['RLIMIT_FSIZE'] == [1 << 20]*2


@pytest.mark.integration
def test_cancelled_capture_reaps_child_and_closes_pipes():
    cancelled=threading.Event()
    timer=threading.Timer(0.2,cancelled.set); timer.start()
    started=time.monotonic()
    try:
        with pytest.raises(media.DecodeCancelled) as failure:
            run('import time;time.sleep(30)',cancel_event=cancelled)
    finally: timer.cancel()
    assert time.monotonic()-started < 4
    assert failure.value.execution_receipt['reaped'] is True


def test_dimensions_and_total_work_are_separate_from_resident_buffer():
    from backend.app.workbench.contracts import SourceClockIdentity
    p=policy(max_buffer_bytes=24, max_frames=10)
    identity=SourceClockIdentity(sourceSha256='a'*64,byteSize=1,width=2,height=2)
    assert p.decode_budget(identity) == (12,120)
    with pytest.raises(media.MediaResourceLimit,match='buffer'):
        policy(max_buffer_bytes=23).decode_budget(identity)
    assert policy(max_buffer_bytes=24,max_frames=10,max_decoded_bytes=13).decode_budget(identity)==(12,13)


@pytest.mark.integration
def test_cpu_hard_limit_after_handled_soft_signal_is_not_generic_oom_proof():
    with pytest.raises(media.DecoderFailed) as failure:
        run('import signal,sys\nsignal.signal(signal.SIGXCPU,lambda *args:print("soft received",file=sys.stderr,flush=True))\nwhile True: pass',
            p=policy(cpu_soft_seconds=1,cpu_hard_seconds=2))
    assert failure.value.code == -signal.SIGKILL
    assert any('soft received' in line for line in failure.value.tail)
    assert failure.value.execution_receipt['enforcedLimits']['RLIMIT_CPU']==[1,2]
    assert failure.value.execution_receipt['outcome']=='CHILD_SIGNAL_UNKNOWN'
    assert failure.value.execution_receipt['reaped']


@pytest.mark.integration
def test_cancel_kills_process_group_and_parent_reaps_its_child(tmp_path):
    import os
    parent_ready=tmp_path/'ready.json'
    code=('import os,signal,json,time\n'
          'child=os.fork()\n'
          'if child==0:\n time.sleep(30);os._exit(0)\n'
          'def done(*args):\n os.waitpid(child,0);os._exit(0)\n'
          'signal.signal(signal.SIGTERM,done)\n'
          f'open({str(parent_ready)!r},"w").write(json.dumps([os.getpid(),child]))\n'
          'while True: time.sleep(.01)\n')
    cancel=threading.Event()
    def cancel_when_ready():
        until=time.monotonic()+5
        while not parent_ready.exists() and time.monotonic()<until: time.sleep(.01)
        cancel.set()
    thread=threading.Thread(target=cancel_when_ready);thread.start()
    try:
        with pytest.raises(media.DecodeCancelled) as failure:
            run(code,cancel_event=cancel)
    finally: thread.join(timeout=6)
    parent,child=json.loads(parent_ready.read_text())
    assert failure.value.execution_receipt['reaped']
    for pid in (parent,child):
        with pytest.raises(ProcessLookupError): os.kill(pid,0)


def test_unqualified_platform_refuses_before_child_launch(tmp_path,monkeypatch):
    from backend.app.workbench import media_execution
    monkeypatch.setattr(media_execution.sys,'platform','darwin')
    with pytest.raises(media.MediaResourceLimit,match='PLATFORM_NOT_QUALIFIED'):
        media_execution.MediaExecution([sys.executable,'-V'],policy=policy(),cwd=tmp_path,
                                        timeout=5,popen=lambda *a,**k:pytest.fail('must not start child'))


def test_cpu_decode_and_tensor_runtime_are_independent_capabilities(monkeypatch):
    from backend.app.workbench import native
    monkeypatch.setattr(native,'_detect_cuda',lambda:{'nvidia':True,'torch':True})
    assert native.probe_gpu().available is True
    assert native.cuda_visibility_is_not_video_capability(cuda_visible=True)['videoEngineCapability'] is False
    assert media.cpu_fallback('cuda',{'opencv'})=='opencv'


def test_pre_cancelled_capture_never_starts_a_child(monkeypatch):
    cancel=threading.Event();cancel.set()
    monkeypatch.setattr(media.subprocess,'Popen',lambda *a,**k:pytest.fail('pre-cancelled child started'))
    with pytest.raises(media.DecodeCancelled):
        run('print("must not execute")',cancel_event=cancel)
