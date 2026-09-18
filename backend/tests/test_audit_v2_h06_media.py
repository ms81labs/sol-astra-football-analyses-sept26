from __future__ import annotations

import hashlib
import io
import json
import multiprocessing
import resource
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.workbench.hashing import HashCache, stream_sha256
from backend.app.workbench.media import (
    DecodeCancelled,
    DecodedFrame,
    DecoderFailed,
    FfmpegFrameSource,
    FfmpegProbe,
    MediaResourceLimit,
    TruncatedStream,
    _run_bounded_media_process,
    should_export_on_source_grid,
)


def _hash_under_limit(path: str, expected: str, queue) -> None:
    resource.setrlimit(resource.RLIMIT_AS, (128 << 20, 128 << 20))
    queue.put(stream_sha256(Path(path)).sha256 == expected)


@pytest.mark.integration
def test_t15_stream_hash_is_bounded_and_cache_avoids_reread(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "large.bin"
    with source.open("wb") as handle:
        handle.truncate(300 << 20)
    expected = hashlib.sha256()
    with source.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            expected.update(chunk)

    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    process = context.Process(target=_hash_under_limit, args=(str(source), expected.hexdigest(), queue))
    process.start()
    process.join(30)
    assert process.exitcode == 0
    assert queue.get(timeout=1) is True

    cache = HashCache(tmp_path)
    assert cache.identity(source).sha256 == expected.hexdigest()
    original_open = Path.open

    def reject_source_open(path: Path, *args, **kwargs):
        if path.resolve() == source.resolve():
            raise AssertionError("cached file was re-read")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", reject_source_open)
    assert cache.identity(source).sha256 == expected.hexdigest()


def test_t15_hashing_sites_do_not_use_read_bytes() -> None:
    repository = Path(__file__).resolve().parents[2]
    for relative in (
        "backend/app/workbench/media.py",
        "backend/app/video_pipeline.py",
        "backend/app/remote_worker.py",
        "backend/app/storage.py",
    ):
        source = (repository / relative).read_text(encoding="utf-8")
        assert "read_bytes()" not in source


def test_t15_hash_cache_concurrent_writers_keep_every_entry(tmp_path: Path) -> None:
    sources = []
    for index in range(32):
        source = tmp_path / f"source-{index}.bin"
        source.write_bytes(str(index).encode())
        sources.append(source)

    with ThreadPoolExecutor(max_workers=16) as pool:
        identities = list(pool.map(lambda path: HashCache(tmp_path).identity(path), sources))

    cache = json.loads((tmp_path / ".hash-cache.json").read_text(encoding="utf-8"))
    assert len(identities) == len(cache) == 32


def test_t18_fractional_time_base_preserves_integer_pts() -> None:
    frame = DecodedFrame(
        source_frame_index=0,
        pts=30,
        presentation_time_seconds=float(Fraction(30 * 1001, 30_000)),
        width=1,
        height=1,
        colour_order="bgr",
        rotation=0,
        payload=b"\0\0\0",
        backend="fixture",
        time_base=(1001, 30_000),
    )
    assert frame.presentation_time == Fraction(30_030, 30_000)
    assert frame.pts == 30


def test_t18_integer_pts_grid_is_origin_anchored_and_skips_duplicates() -> None:
    selected: list[int] = []
    last: int | None = None
    for index, pts in enumerate((0, 0, 2, 3, 5, 6, 9)):
        if should_export_on_source_grid(
            float(Fraction(pts * 1001, 30_000)),
            frame_count=index,
            frame_interval=3,
            last_export_presentation_time=None,
            grid_step_seconds=0.1,
            pts=pts,
            time_base=(1001, 30_000),
            last_export_pts=last,
            grid_origin_pts=0,
            target_fps=10,
        ):
            selected.append(pts)
            last = pts
    assert selected == [0, 3, 6, 9]


def test_t27_resolved_media_tools_are_absolute_and_trusted(tmp_path: Path) -> None:
    from backend.app.workbench.executables import resolve_trusted_executable

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("ffmpeg unavailable")
    resolved = resolve_trusted_executable("ffmpeg", configured=ffmpeg)
    assert resolved.is_absolute()
    with pytest.raises(ValueError):
        resolve_trusted_executable("ffmpeg", configured="ffmpeg")
    with pytest.raises(ValueError):
        resolve_trusted_executable("ffmpeg", configured="http://example.test/ffmpeg")
    untrusted = tmp_path / "ffmpeg"
    shutil.copyfile(ffmpeg, untrusted)
    untrusted.chmod(0o755)
    try:
        with pytest.raises(ValueError):
            resolve_trusted_executable("ffmpeg", configured=str(untrusted))
    finally:
        untrusted.unlink(missing_ok=True)


def test_t27_custom_trust_policy_reaches_both_media_guards(tmp_path: Path) -> None:
    from backend.app.workbench.access import constrained_decoder
    from backend.app.workbench.media import FfmpegProbe, _assert_safe_ffmpeg_argv

    source = shutil.which("ffmpeg")
    if source is None:
        pytest.skip("ffmpeg unavailable")
    custom = tmp_path / "ffmpeg"
    shutil.copyfile(source, custom)
    custom.chmod(0o755)
    settings = SimpleNamespace(
        trusted_bin_dirs=(str(tmp_path),),
        ffmpeg_sha256=None,
        ffprobe_sha256=None,
    )
    probe = FfmpegProbe(ffmpeg=str(custom), settings=settings)
    command = [probe.ffmpeg, "-version"]

    _assert_safe_ffmpeg_argv(command, settings=settings)
    assert constrained_decoder(argv=command, network_enabled=False, settings=settings)["admitted"] is True


@pytest.mark.real_media
def test_t16_t18_real_ffmpeg_frames_match_ffprobe_integer_pts(tmp_path: Path) -> None:
    from backend.app.workbench.executables import resolve_trusted_executable

    ffmpeg = resolve_trusted_executable("ffmpeg")
    ffprobe = resolve_trusted_executable("ffprobe")
    clip = tmp_path / "fractional.mp4"
    subprocess.run(
        [
            str(ffmpeg), "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
            "testsrc=duration=0.4:size=32x24:rate=30000/1001", "-pix_fmt", "yuv420p", "-y", str(clip),
        ],
        check=True,
        timeout=30,
    )
    expected = subprocess.run(
        [
            str(ffprobe), "-v", "error", "-select_streams", "v:0", "-show_frames",
            "-show_entries", "frame=pts", "-of", "json", str(clip),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    expected_pts = [int(frame["pts"]) for frame in json.loads(expected.stdout)["frames"]]

    frames = list(FfmpegFrameSource().iter_frames(clip))

    assert [frame.pts for frame in frames] == expected_pts
    assert all(frame.presentation_time == Fraction(frame.pts, 30_000) for frame in frames)


@pytest.mark.real_media
def test_t16_real_ffmpeg_reaps_malformed_and_output_capped_children(tmp_path: Path, monkeypatch) -> None:
    from backend.app.workbench.executables import resolve_trusted_executable
    import backend.app.workbench.media as media

    ffmpeg = resolve_trusted_executable("ffmpeg")
    clip = tmp_path / "bounded.mp4"
    subprocess.run(
        [
            str(ffmpeg), "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
            "testsrc=duration=1:size=32x24:rate=4", "-movflags", "+faststart",
            "-pix_fmt", "yuv420p", "-y", str(clip),
        ],
        check=True,
        timeout=30,
    )
    identity = FfmpegProbe().probe_identity(clip)
    malformed = tmp_path / "truncated.mp4"
    payload = clip.read_bytes()
    malformed.write_bytes(payload[: len(payload) // 2])
    with pytest.raises((DecoderFailed, TruncatedStream)):
        list(FfmpegFrameSource().iter_frames(malformed))

    processes = []
    popen = subprocess.Popen

    def capture(*args, **kwargs):
        process = popen(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(media.subprocess, "Popen", capture)
    with pytest.raises(MediaResourceLimit, match="output-byte cap"):
        list(FfmpegFrameSource(identity=identity, max_output_bytes=32 * 24 * 3 + 1).iter_frames(clip))
    assert len(processes) == 1
    assert processes[0].poll() is not None


class _FakeProcess:
    def __init__(self, stdout: bytes, stderr: bytes, *, code: int = 0, delay: float = 0.0):
        self.stdout = io.BytesIO(stdout)
        self.stderr = _DelayedBytes(stderr, delay)
        self.code = code
        self.returncode: int | None = None

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        del timeout
        self.returncode = self.code
        return self.code

    def kill(self):
        self.returncode = -9


class _DelayedBytes(io.BytesIO):
    def __init__(self, payload: bytes, delay: float):
        super().__init__(payload)
        self.delay = delay

    def read(self, size=-1):
        if self.delay:
            time.sleep(self.delay)
            self.delay = 0
        return super().read(size)


def _fake_source(tmp_path: Path) -> tuple[Path, FfmpegFrameSource]:
    from backend.app.workbench.contracts import SourceClockIdentity

    path = tmp_path / "input.mp4"
    path.write_bytes(b"source")
    identity = SourceClockIdentity(
        sourceSha256="a" * 64,
        byteSize=6,
        width=2,
        height=2,
        timeBaseNum=1,
        timeBaseDen=25,
    )
    return path, FfmpegFrameSource(identity=identity)


def test_t16_decoder_handles_delayed_or_missing_stderr_and_failures(tmp_path: Path, monkeypatch) -> None:
    path, source = _fake_source(tmp_path)
    frame = bytes(range(12))
    processes = iter(
        (
            _FakeProcess(frame, b"n:0 pts:1 pts_time:0.04\n", delay=0.05),
            _FakeProcess(frame, b""),
            _FakeProcess(frame[:5], b""),
            _FakeProcess(b"", b"failure\n" * 300, code=1),
        )
    )
    monkeypatch.setattr("backend.app.workbench.media.subprocess.Popen", lambda *args, **kwargs: next(processes))

    assert list(source.iter_frames(path))[0].pts == 1
    missing = list(source.iter_frames(path))[0]
    assert missing.pts is None and missing.presentation_clock == "missing"
    with pytest.raises(TruncatedStream):
        list(source.iter_frames(path))
    with pytest.raises(DecoderFailed) as failed:
        list(source.iter_frames(path))
    assert failed.value.code == 1
    assert len(failed.value.tail) <= 256


def test_t16_cancel_terminates_decoder(tmp_path: Path, monkeypatch) -> None:
    path, source = _fake_source(tmp_path)
    process = _FakeProcess(bytes(range(12)), b"")
    monkeypatch.setattr("backend.app.workbench.media.subprocess.Popen", lambda *args, **kwargs: process)
    cancelled = threading.Event()
    cancelled.set()

    with pytest.raises(DecodeCancelled):
        list(source.iter_frames(path, cancel_event=cancelled))
    assert process.poll() is not None


def test_t16_decoder_output_cap_terminates_child(tmp_path: Path, monkeypatch) -> None:
    path, source = _fake_source(tmp_path)
    source = FfmpegFrameSource(identity=source._identity, max_output_bytes=11)
    monkeypatch.setattr(
        "backend.app.workbench.media.subprocess.Popen",
        lambda *args, **kwargs: pytest.fail("oversized declared frame reached Popen"),
    )

    with pytest.raises(MediaResourceLimit, match="output-byte cap"):
        list(source.iter_frames(path))


def test_t16_decoder_thread_limit_applies_before_input(tmp_path: Path, monkeypatch) -> None:
    path, source = _fake_source(tmp_path)
    commands: list[list[str]] = []

    def popen(command, **_kwargs):
        commands.append(command)
        return _FakeProcess(bytes(range(12)), b"")

    monkeypatch.setattr("backend.app.workbench.media.subprocess.Popen", popen)

    assert len(list(source.iter_frames(path))) == 1
    assert commands[0].index("-threads") < commands[0].index("-i")


@pytest.mark.integration
def test_t16_live_child_output_cap_and_mid_export_cancellation(tmp_path: Path, monkeypatch) -> None:
    with pytest.raises(MediaResourceLimit, match="captured-output cap"):
        _run_bounded_media_process(
            [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'x' * 2000000)"],
            timeout=10,
            output_cap=1024,
            file_cap=1 << 20,
        )

    ffmpeg = tmp_path / "ffmpeg"
    ffmpeg.write_text("#!/bin/sh\nexec sleep 30\n", encoding="utf-8")
    ffmpeg.chmod(0o755)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"fixture")
    settings = SimpleNamespace(
        trusted_bin_dirs=(str(tmp_path),), ffmpeg_sha256=None, ffprobe_sha256=None
    )
    probe = FfmpegProbe(ffmpeg=str(ffmpeg), settings=settings)
    import backend.app.workbench.media as media

    processes = []
    popen = subprocess.Popen

    def capture(*args, **kwargs):
        process = popen(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(media.subprocess, "Popen", capture)
    cancelled = threading.Event()
    timer = threading.Timer(0.2, cancelled.set)
    timer.start()
    started = time.monotonic()
    try:
        with pytest.raises(DecodeCancelled):
            probe.export_clip(
                source,
                tmp_path / "cancelled.mp4",
                start_seconds=0,
                duration_seconds=1,
                cancel_event=cancelled,
            )
    finally:
        timer.cancel()
    assert time.monotonic() - started < 5
    assert len(processes) == 1
    assert processes[0].poll() is not None


def test_t18_duplicate_decoder_pts_are_flagged(tmp_path: Path, monkeypatch) -> None:
    path, source = _fake_source(tmp_path)
    process = _FakeProcess(
        bytes(range(12)) * 2,
        b"n:0 pts:4 pts_time:0.16\nn:1 pts:4 pts_time:0.16\n",
    )
    monkeypatch.setattr("backend.app.workbench.media.subprocess.Popen", lambda *args, **kwargs: process)

    frames = list(source.iter_frames(path))

    assert [frame.duplicate_pts for frame in frames] == [False, True]
