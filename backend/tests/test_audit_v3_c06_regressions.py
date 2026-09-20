"""Baseline-compatible counterexamples for C06; no new API is needed."""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.workbench import media


def _clip(path: Path) -> Path:
    subprocess.run([
        str(media.resolve_trusted_executable('ffmpeg')), '-hide_banner', '-loglevel', 'error',
        '-f', 'lavfi', '-i', 'color=black:size=32x24:rate=4:duration=1',
        '-threads', '1', '-pix_fmt', 'yuv420p', '-y', str(path),
    ], check=True, timeout=15)
    return path


@pytest.mark.integration
def test_media_child_does_not_execute_python_preexec_in_threaded_parent(tmp_path, monkeypatch):
    seen = []
    popen = subprocess.Popen
    def launch(*args, **kwargs):
        seen.append(kwargs.copy())
        return popen(*args, **kwargs)
    monkeypatch.setattr(media.subprocess, 'Popen', launch)
    result = media._run_bounded_media_process(
        [sys.executable, '-I', '-S', '-c', 'print("real child")'],
        timeout=5, output_cap=65536, file_cap=1 << 20,
    )
    assert b'real child' in result.stdout
    assert seen and all(not kw.get('preexec_fn') for kw in seen)


@pytest.mark.real_media
def test_proxy_uses_the_existing_bounded_media_boundary(tmp_path, monkeypatch):
    source = _clip(tmp_path / 'original with spaces.mp4')
    before = source.read_bytes()
    calls = []
    bounded = media._run_bounded_media_process
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return bounded(command, **kwargs)
    monkeypatch.setattr(media, '_run_bounded_media_process', run)
    media.run_proxy_ffmpeg_job(source, tmp_path / 'proxy.mp4',
        original_sha256=hashlib.sha256(before).hexdigest(), proxy_height=24)
    assert source.read_bytes() == before
    assert calls, 'proxy bypassed the common bounded process boundary'
    assert all('-protocol_whitelist' in command for command, _ in calls)


def test_failed_export_does_not_replace_an_existing_artifact(tmp_path):
    source = tmp_path / 'input.mp4'; source.write_bytes(b'original')
    output = tmp_path / 'out.mp4'; output.write_bytes(b'previous valid artifact')
    def fails(command, **kwargs):
        Path(command[-1]).write_bytes(b'partial output')
        raise subprocess.CalledProcessError(1, command)
    with pytest.raises(subprocess.CalledProcessError):
        media.FfmpegProbe().export_clip(source, output, start_seconds=0,
                                      duration_seconds=1, runner=fails)
    assert output.read_bytes() == b'previous valid artifact'
    assert source.read_bytes() == b'original'


def test_proxy_refuses_original_as_destination_before_any_write(tmp_path):
    source = tmp_path / 'original.mp4'; source.write_bytes(b'original')
    def corrupts(command, **kwargs):
        Path(command[-1]).write_bytes(b'overwritten')
        return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
    with pytest.raises(ValueError):
        media.run_proxy_ffmpeg_job(source, source,
            original_sha256=hashlib.sha256(b'original').hexdigest(), runner=corrupts)
    assert source.read_bytes() == b'original'


@pytest.mark.parametrize('duration', [float('nan'), float('inf'), -1.0, 0.0])
def test_invalid_export_duration_is_rejected_before_execution(tmp_path, duration):
    source = tmp_path / 'original.mp4'; source.write_bytes(b'original')
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        Path(command[-1]).write_bytes(b'output')
        return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
    with pytest.raises(ValueError):
        media.FfmpegProbe().export_clip(source, tmp_path / 'out.mp4',
            start_seconds=0, duration_seconds=duration, runner=runner)
    assert not calls
