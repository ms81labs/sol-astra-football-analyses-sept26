"""C06 recovery review: source admission remains binding until publication."""
from __future__ import annotations
import hashlib
from pathlib import Path
import pytest
from backend.app.workbench import media
from backend.app.workbench.media_execution import MediaExecutionPolicy
from backend.tests.test_audit_v3_c06_media import clip


@pytest.mark.real_media
def test_decoder_records_admission_refusal(tmp_path):
    source = clip(tmp_path / "long.mp4", duration=2)
    decoder = media.FfmpegFrameSource(policy=MediaExecutionPolicy(max_duration_seconds=1))
    with pytest.raises(media.MediaResourceLimit, match="SOURCE_NOT_ADMITTED"):
        list(decoder.iter_frames(source))
    assert decoder.last_execution_receipt["outcome"] == "SOURCE_NOT_ADMITTED"
    assert decoder.last_execution_receipt["published"] is False


@pytest.mark.real_media
@pytest.mark.parametrize("operation", ["decode", "export", "proxy"])
def test_changed_source_after_probe_never_decodes_or_publishes(tmp_path, monkeypatch, operation):
    source = clip(tmp_path / "input.mp4")
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    output = tmp_path / "output.mp4"
    output.write_bytes(b"previous valid artifact")
    original_probe = media.FfmpegProbe.probe_identity
    calls = []
    process = media.MediaExecution

    def capture(command, **kwargs):
        calls.append(Path(command[0]).name)
        return process(command, **kwargs)

    def changed_after_probe(self, path, **kwargs):
        result = original_probe(self, path, **kwargs)
        if Path(path).resolve() == source.resolve():
            with source.open("ab") as handle:
                handle.write(b"changed between probe and launch")
        return result

    monkeypatch.setattr(media, "MediaExecution", capture)
    monkeypatch.setattr(media.FfmpegProbe, "probe_identity", changed_after_probe)
    with pytest.raises(ValueError):
        if operation == "decode":
            list(media.FfmpegFrameSource().iter_frames(source))
        elif operation == "export":
            media.FfmpegProbe().export_clip(source, output, start_seconds=0, duration_seconds=.5)
        else:
            media.run_proxy_ffmpeg_job(source, output, original_sha256=sha, proxy_height=24)
    assert output.read_bytes() == b"previous valid artifact"
    assert calls == ["ffprobe"], "changed source reached media transform after admission"
    assert not list(tmp_path.glob(".ga-media-*"))
