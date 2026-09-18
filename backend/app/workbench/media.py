"""GA-02 source-clock identity, GA-15 sampling audit, GA-16 FrameSource adapters."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import threading
import time
import tempfile
from fractions import Fraction
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterator, Literal

from .contracts import FrameIdentity, SamplingReceipt, SourceClockIdentity
from .access import constrained_decoder
from .hashing import HashCache, stream_sha256
from .executables import resolve_trusted_executable


ColourOrder = Literal["bgr", "rgb"]


def _file_identity(path: Path, cache: HashCache | None):
    return cache.identity(path) if cache is not None else stream_sha256(path)


@dataclass(frozen=True)
class DecodedFrame:
    source_frame_index: int
    pts: int | None
    presentation_time_seconds: float | None
    width: int
    height: int
    colour_order: ColourOrder
    rotation: int
    payload: bytes
    backend: str
    crop: tuple[int, int, int, int] | None = None
    image: object | None = None
    buffer: FrameBuffer | None = None
    presentation_clock: Literal["decoder_pts", "missing"] = "decoder_pts"
    time_base: tuple[int, int] = (1, 1000)
    duplicate_pts: bool = False

    @property
    def presentation_time(self) -> Fraction | None:
        if self.pts is None or self.presentation_clock == "missing":
            return None
        numerator, denominator = self.time_base
        return Fraction(self.pts * numerator, denominator)


class DecodeCancelled(RuntimeError):
    pass


class TruncatedStream(RuntimeError):
    pass


class DecoderFailed(RuntimeError):
    def __init__(self, code: int, *, tail: list[str]):
        super().__init__(f"decoder exited with code {code}")
        self.code = code
        self.tail = tail


class MediaResourceLimit(RuntimeError):
    pass


def _sandbox_kwargs(cwd: Path, *, max_file_bytes: int) -> dict[str, object]:
    kwargs: dict[str, object] = {"cwd": cwd}
    if os.name != "posix":
        return kwargs

    def limits() -> None:
        import resource

        for name, value in (
            ("RLIMIT_AS", 4 * 1024**3),
            ("RLIMIT_CPU", 300),
            ("RLIMIT_FSIZE", max_file_bytes),
        ):
            limit = getattr(resource, name, None)
            if limit is not None:
                resource.setrlimit(limit, (value, value))

    kwargs["preexec_fn"] = limits
    return kwargs


class _ShowinfoParser:
    _pattern = re.compile(
        rb"\bn:\s*(?P<n>\d+).*?\bpts:\s*(?P<pts>-?\d+).*?\bpts_time:\s*(?P<time>-?\d+(?:\.\d+)?)"
    )

    def __init__(self) -> None:
        self.carry = b""

    def feed(self, chunk: bytes) -> list[tuple[int, int, float]]:
        lines = (self.carry + chunk).split(b"\n")
        self.carry = lines.pop()
        return self._parse(lines)

    def finish(self) -> list[tuple[int, int, float]]:
        lines = [self.carry] if self.carry else []
        self.carry = b""
        return self._parse(lines)

    def _parse(self, lines: list[bytes]) -> list[tuple[int, int, float]]:
        parsed: list[tuple[int, int, float]] = []
        for line in lines:
            match = self._pattern.search(line)
            if match is not None:
                parsed.append(
                    (
                        int(match.group("n")),
                        int(match.group("pts")),
                        float(match.group("time")),
                    )
                )
        return parsed


def _read_exact(stream, size: int) -> bytes | None:
    payload = bytearray()
    while len(payload) < size:
        chunk = stream.read(size - len(payload))
        if not chunk:
            if payload:
                raise TruncatedStream("decoder ended mid-frame")
            return None
        payload.extend(chunk)
    return bytes(payload)


@dataclass
class FrameBuffer:
    """4.5B ownership contract. Football coordinates stay outside this object."""

    device: Literal["cpu", "cuda"]
    shape: tuple[int, ...]
    strides: tuple[int, ...] | None
    dtype: str
    lifetime: Literal["borrowed", "owned"]
    batch_index: int | None
    sync_required: bool
    payload: bytes
    _released: bool = False

    def release(self) -> None:
        self._released = True

    def as_array(self) -> bytes:
        if self._released:
            raise RuntimeError("use after buffer reuse")
        return self.payload


class FrameSource(ABC):
    """Replaceable decode adapter. Football semantics stay in Python."""

    name: str

    @abstractmethod
    def probe(self, path: Path) -> SourceClockIdentity:
        raise NotImplementedError

    @abstractmethod
    def iter_frames(self, path: Path, *, cancel_event: threading.Event | None = None) -> Iterator[DecodedFrame]:
        raise NotImplementedError


class FixtureFrameSource(FrameSource):
    """Deterministic in-memory decoder used for CFR/VFR/cut/off-grid tests."""

    name = "fixture"

    def __init__(self, frames: list[DecodedFrame], identity: SourceClockIdentity, *, hash_cache: HashCache | None = None):
        self._frames = list(frames)
        self._identity = identity
        self._hash_cache = hash_cache

    def probe(self, path: Path) -> SourceClockIdentity:
        identity = _file_identity(path, self._hash_cache) if path.exists() else None
        return self._identity.model_copy(
            update={
                "sourceSha256": identity.sha256 if identity else self._identity.sourceSha256,
                "byteSize": identity.size if identity else 0,
            }
        )

    def iter_frames(self, path: Path, *, cancel_event: threading.Event | None = None) -> Iterator[DecodedFrame]:
        for frame in self._frames:
            if cancel_event is not None and cancel_event.is_set():
                return
            yield frame


class OpenCvFrameSource(FrameSource):
    name = "opencv"

    def __init__(self, cv2_module: object | None = None, *, hash_cache: HashCache | None = None):
        self._cv2 = cv2_module
        self._hash_cache = hash_cache

    def _cv(self):
        if self._cv2 is not None:
            return self._cv2
        import cv2  # type: ignore

        return cv2

    def probe(self, path: Path) -> SourceClockIdentity:
        _admit_local_decode_path(path)
        file_identity = _file_identity(path, self._hash_cache) if path.exists() else None
        identity = SourceClockIdentity(
            sourceSha256=file_identity.sha256 if file_identity else "",
            byteSize=file_identity.size if file_identity else 0,
        )
        try:
            cv2 = self._cv()
        except Exception:
            return identity
        capture = cv2.VideoCapture(str(path))
        opened = True if not hasattr(capture, "isOpened") else bool(capture.isOpened())
        if not opened:
            if hasattr(capture, "release"):
                capture.release()
            return identity.model_copy(update={"decodeErrors": ["opencv_open_failed"]})
        try:
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0) or None
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0) or None
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0) or None
            raw_frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
            frame_count = int(raw_frame_count) if raw_frame_count else None
            duration = (raw_frame_count / fps) if fps and raw_frame_count else None
        except Exception:
            fps = width = height = frame_count = duration = None
        finally:
            if hasattr(capture, "release"):
                capture.release()
        return identity.model_copy(
            update={
                "width": width,
                "height": height,
                "nominalFps": fps,
                "durationSeconds": duration,
                "frameCount": frame_count,
                "pixelFormat": "bgr24",
            }
        )

    def iter_frames(self, path: Path, *, cancel_event: threading.Event | None = None) -> Iterator[DecodedFrame]:
        _admit_local_decode_path(path)
        cv2 = self._cv()
        capture = cv2.VideoCapture(str(path))
        opened = True if not hasattr(capture, "isOpened") else bool(capture.isOpened())
        if not opened:
            if hasattr(capture, "release"):
                capture.release()
            return
        index = 0
        last_msec: float | None = None
        try:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    return
                ok, image = capture.read()
                if not ok:
                    return
                payload = image.tobytes() if hasattr(image, "tobytes") else bytes(image)
                height, width = (int(image.shape[0]), int(image.shape[1])) if hasattr(image, "shape") else (0, 0)
                presentation_time_seconds, pts, clock = _opencv_presentation_clock(
                    capture, cv2, index, last_msec=last_msec
                )
                if clock == "decoder_pts":
                    last_msec = presentation_time_seconds * 1000.0
                yield DecodedFrame(
                    source_frame_index=index,
                    pts=pts,
                    presentation_time_seconds=presentation_time_seconds,
                    width=width,
                    height=height,
                    colour_order="bgr",
                    rotation=0,
                    payload=payload,
                    backend=self.name,
                    image=image,
                    presentation_clock=clock,
                )
                index += 1
        finally:
            capture.release()


class FfmpegFrameSource(FrameSource):
    """GA-16 decoder challenger. Football semantics stay in Python."""

    name = "ffmpeg"

    def __init__(
        self,
        frames: list[DecodedFrame] | None = None,
        identity: SourceClockIdentity | None = None,
        probe: FfmpegProbe | None = None,
        hash_cache: HashCache | None = None,
        max_output_bytes: int = 8 * 1024**3,
        wall_timeout_seconds: float = 300.0,
        threads: int = 2,
    ):
        self._frames = list(frames or [])
        self._identity = identity
        self._hash_cache = hash_cache
        self._probe = probe or FfmpegProbe(hash_cache=hash_cache)
        self._max_output_bytes = max_output_bytes
        self._wall_timeout_seconds = wall_timeout_seconds
        self._threads = threads

    def probe(self, path: Path) -> SourceClockIdentity:
        if self._identity is not None:
            identity = _file_identity(path, self._hash_cache) if path.exists() else None
            return self._identity.model_copy(
                update={
                    "sourceSha256": identity.sha256 if identity else self._identity.sourceSha256,
                    "byteSize": identity.size if identity else 0,
                }
            )
        return self._probe.probe_identity(path)

    def iter_frames(self, path: Path, *, cancel_event: threading.Event | None = None) -> Iterator[DecodedFrame]:
        if self._frames:
            if path.exists():
                with path.open("rb") as handle:
                    handle.read(1)
            for frame in self._frames:
                if cancel_event is not None and cancel_event.is_set():
                    return
                yield frame
            return
        yield from self._iter_ffmpeg_decode(path, cancel_event=cancel_event)

    def _iter_ffmpeg_decode(self, path: Path, *, cancel_event: threading.Event | None) -> Iterator[DecodedFrame]:
        _admit_local_decode_path(path)
        path = path.resolve()
        identity = self._identity or self.probe(path)
        width = int(identity.width or 0)
        height = int(identity.height or 0)
        if width <= 0 or height <= 0:
            raise RuntimeError("ffmpeg decode requires probed width and height")
        frame_size = width * height * 3
        if frame_size > self._max_output_bytes:
            raise MediaResourceLimit("ffmpeg decode exceeded output-byte cap")
        command = [
            self._probe.ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-loglevel",
            "info",
            "-protocol_whitelist",
            "file,pipe",
            "-threads",
            str(self._threads),
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-an",
            "-vf",
            "showinfo",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "pipe:1",
        ]
        decision = constrained_decoder(argv=command, network_enabled=False, settings=self._probe.settings)
        if not decision["admitted"]:
            raise ValueError("unconstrained decoder")
        _assert_safe_ffmpeg_argv(command, settings=self._probe.settings)
        scratch = tempfile.TemporaryDirectory(prefix="ga-ffmpeg-decode-")
        process = subprocess.Popen(  # noqa: S603
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            **_sandbox_kwargs(Path(scratch.name), max_file_bytes=self._max_output_bytes),
        )
        assert process.stdout is not None
        assert process.stderr is not None
        index = 0
        condition = threading.Condition()
        pts_by_index: dict[int, tuple[int, float]] = {}
        diagnostics: deque[str] = deque(maxlen=256)
        stderr_done = False

        def read_stderr() -> None:
            nonlocal stderr_done
            parser = _ShowinfoParser()
            try:
                while chunk := (
                    process.stderr.read1(65536)
                    if hasattr(process.stderr, "read1")
                    else process.stderr.read(65536)
                ):
                    lines = chunk.decode("utf-8", errors="replace").splitlines()
                    diagnostics.extend(lines)
                    parsed = parser.feed(chunk)
                    if parsed:
                        with condition:
                            for frame_index, pts, pts_time in parsed:
                                pts_by_index[frame_index] = (pts, pts_time)
                            condition.notify_all()
                parsed = parser.finish()
                if parsed:
                    with condition:
                        for frame_index, pts, pts_time in parsed:
                            pts_by_index[frame_index] = (pts, pts_time)
                        condition.notify_all()
            finally:
                with condition:
                    stderr_done = True
                    condition.notify_all()

        reader = threading.Thread(target=read_stderr, name="ffmpeg-stderr", daemon=True)
        reader.start()
        watcher_stop = threading.Event()
        timed_out = False
        started_at = time.monotonic()

        def watch_cancel() -> None:
            nonlocal timed_out
            while not watcher_stop.wait(0.05):
                if cancel_event is not None and cancel_event.is_set():
                    if process.poll() is None:
                        process.kill()
                    return
                if time.monotonic() - started_at > self._wall_timeout_seconds:
                    timed_out = True
                    if process.poll() is None:
                        process.kill()
                    return

        watcher = threading.Thread(target=watch_cancel, name="ffmpeg-cancel", daemon=True)
        watcher.start()
        cancelled = False
        completed = False
        seen_pts: set[int] = set()
        output_bytes = 0
        try:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    process.kill()
                    cancelled = True
                    break
                try:
                    payload = _read_exact(process.stdout, frame_size)
                except TruncatedStream:
                    if cancel_event is not None and cancel_event.is_set():
                        raise DecodeCancelled("ffmpeg decode cancelled") from None
                    raise
                if payload is None:
                    if cancel_event is not None and cancel_event.is_set():
                        cancelled = True
                    completed = True
                    break
                output_bytes += len(payload)
                if output_bytes > self._max_output_bytes:
                    process.kill()
                    raise MediaResourceLimit("ffmpeg decode exceeded output-byte cap")
                deadline = time.monotonic() + 5.0
                with condition:
                    while index not in pts_by_index and not stderr_done:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            break
                        condition.wait(timeout=remaining)
                    timing = pts_by_index.pop(index, None)
                pts = None if timing is None else timing[0]
                clock: Literal["decoder_pts", "missing"] = (
                    "decoder_pts" if pts is not None else "missing"
                )
                time_base = (int(identity.timeBaseNum or 1), int(identity.timeBaseDen or 1))
                presentation = (
                    None
                    if pts is None
                    else float(Fraction(pts * time_base[0], time_base[1]))
                )
                duplicate = pts in seen_pts if pts is not None else False
                if pts is not None:
                    seen_pts.add(pts)
                yield DecodedFrame(
                    source_frame_index=index,
                    pts=pts,
                    presentation_time_seconds=presentation,
                    width=width,
                    height=height,
                    colour_order="bgr",
                    rotation=int(identity.rotation or 0),
                    payload=payload,
                    backend=self.name,
                    presentation_clock=clock,
                    time_base=time_base,
                    duplicate_pts=duplicate,
                )
                index += 1
            returncode = process.wait(timeout=5)
            reader.join(timeout=5)
            if reader.is_alive():
                raise DecoderFailed(returncode, tail=list(diagnostics))
            if cancelled:
                raise DecodeCancelled("ffmpeg decode cancelled")
            if timed_out:
                raise MediaResourceLimit("ffmpeg decode exceeded wall-clock timeout")
            if returncode != 0:
                raise DecoderFailed(returncode, tail=list(diagnostics))
            if not completed:
                raise TruncatedStream("decoder did not complete cleanly")
        except TruncatedStream:
            try:
                returncode = process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                returncode = process.wait(timeout=5)
            reader.join(timeout=5)
            if returncode != 0:
                raise DecoderFailed(returncode, tail=list(diagnostics)) from None
            raise
        finally:
            watcher_stop.set()
            if process.poll() is None:
                process.kill()
            try:
                process.wait(timeout=5)
            except Exception:
                pass
            process.stdout.close()
            process.stderr.close()
            reader.join(timeout=5)
            watcher.join(timeout=5)
            scratch.cleanup()


def wrap_decoded_frame(frame: DecodedFrame, *, device: Literal["cpu", "cuda"] = "cpu") -> FrameBuffer:
    """4.5B: borrowed CPU buffer. GPU residency is not promoted from CUDA visibility."""

    return FrameBuffer(
        device=device,
        shape=(frame.height, frame.width, 3),
        strides=None,
        dtype="uint8",
        lifetime="borrowed",
        batch_index=None,
        sync_required=device == "cuda",
        payload=frame.payload,
    )


def pixels_from_decoded_frame(frame: DecodedFrame):
    """Production pixels come from the live FrameBuffer, never a released predecessor."""

    buffer = frame.buffer
    if buffer is None:
        raise RuntimeError("decoded frame has no live buffer")
    payload = buffer.as_array()
    import numpy as np

    return np.frombuffer(payload, dtype=np.uint8).reshape(buffer.shape).copy()


def iter_bgr_frames(
    path: Path,
    source: FrameSource | None = None,
    *,
    cancel_event: threading.Event | None = None,
    cv2_module: object | None = None,
) -> Iterator[DecodedFrame]:
    """Production decode iterator. Football semantics stay outside this boundary."""

    adapter = source or OpenCvFrameSource(cv2_module=cv2_module)
    previous: FrameBuffer | None = None
    for frame in adapter.iter_frames(path, cancel_event=cancel_event):
        if previous is not None:
            previous.release()
        buffer = wrap_decoded_frame(frame, device="cpu")
        previous = buffer
        yield replace(frame, buffer=buffer)


def first_bgr_frame(
    path: Path,
    source: FrameSource | None = None,
    *,
    cv2_module: object | None = None,
) -> DecodedFrame | None:
    for frame in iter_bgr_frames(path, source, cv2_module=cv2_module):
        return frame
    return None


def _run_bounded_media_process(
    command: list[str],
    *,
    timeout: float,
    output_cap: int,
    file_cap: int,
    cancel_event: threading.Event | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run a media child with bounded captured output and cooperative cancellation."""

    with tempfile.TemporaryDirectory(prefix="ga-media-child-") as scratch:
        process = subprocess.Popen(  # noqa: S603
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **_sandbox_kwargs(Path(scratch), max_file_bytes=file_cap),
        )
        assert process.stdout is not None and process.stderr is not None
        chunks: dict[str, list[bytes]] = {"stdout": [], "stderr": []}
        size = 0
        lock = threading.Lock()
        overflow = threading.Event()

        def drain(name: str, stream) -> None:
            nonlocal size
            while chunk := stream.read(65536):
                with lock:
                    size += len(chunk)
                    if size > output_cap:
                        overflow.set()
                        if process.poll() is None:
                            process.kill()
                        return
                    chunks[name].append(chunk)

        readers = [
            threading.Thread(target=drain, args=(name, stream), daemon=True)
            for name, stream in (("stdout", process.stdout), ("stderr", process.stderr))
        ]
        for reader in readers:
            reader.start()
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            if cancel_event is not None and cancel_event.wait(0.05):
                process.kill()
                process.wait(timeout=5)
                raise DecodeCancelled("ffmpeg process cancelled")
            if time.monotonic() >= deadline:
                process.kill()
                process.wait(timeout=5)
                raise MediaResourceLimit("ffmpeg process exceeded wall-clock timeout")
            time.sleep(0.05)
        returncode = process.wait(timeout=5)
        for reader in readers:
            reader.join(timeout=5)
        stdout = b"".join(chunks["stdout"])
        stderr = b"".join(chunks["stderr"])
        if overflow.is_set():
            raise MediaResourceLimit("ffmpeg process exceeded captured-output cap")
        if returncode != 0:
            raise DecoderFailed(returncode, tail=stderr.decode(errors="replace").splitlines()[-256:])
        return subprocess.CompletedProcess(command, returncode, stdout, stderr)


class FfmpegProbe:
    """GA-16 FFmpeg/ffprobe jobs with safe arguments and cancellation."""

    def __init__(
        self,
        ffprobe: str | None = None,
        ffmpeg: str | None = None,
        *,
        settings=None,
        hash_cache: HashCache | None = None,
        max_output_bytes: int = 8 * 1024**3,
        threads: int = 2,
    ):
        self.settings = settings
        self.hash_cache = hash_cache
        self.ffprobe = str(resolve_trusted_executable("ffprobe", configured=ffprobe, settings=settings))
        self.ffmpeg = str(resolve_trusted_executable("ffmpeg", configured=ffmpeg, settings=settings))
        self.max_output_bytes = max_output_bytes
        self.threads = threads

    def probe_identity(self, path: Path, *, runner=subprocess.run) -> SourceClockIdentity:
        _admit_local_decode_path(path)
        path = path.resolve()
        command = [
            self.ffprobe,
            "-protocol_whitelist",
            "file,pipe",
            "-threads",
            str(self.threads),
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        _assert_safe_ffmpeg_argv(command, settings=self.settings)
        if runner is subprocess.run:
            completed = _run_bounded_media_process(
                command, timeout=30, output_cap=4 * 1024**2, file_cap=self.max_output_bytes
            )
            stdout = completed.stdout.decode("utf-8")
        else:
            stdout = runner(command, check=True, capture_output=True, text=True, timeout=30).stdout
        payload = json.loads(stdout)
        video = next((stream for stream in payload.get("streams", []) if stream.get("codec_type") == "video"), {})
        audio_tracks = sum(1 for stream in payload.get("streams", []) if stream.get("codec_type") == "audio")
        num, den = _parse_rate(video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1")
        time_base_num, time_base_den = _parse_rate(video.get("time_base") or "1/1")
        fps = (num / den) if den else None
        duration = float(payload.get("format", {}).get("duration") or 0.0) or None
        file_identity = _file_identity(path, self.hash_cache)
        return SourceClockIdentity(
            sourceSha256=file_identity.sha256,
            byteSize=file_identity.size,
            codec=video.get("codec_name"),
            width=int(video["width"]) if video.get("width") else None,
            height=int(video["height"]) if video.get("height") else None,
            rotation=_rotation_from_tags(video),
            pixelFormat=video.get("pix_fmt"),
            timeBaseNum=time_base_num,
            timeBaseDen=time_base_den,
            nominalFps=fps,
            durationSeconds=duration,
            variableFrameRate=_is_vfr(video),
            audioTracks=audio_tracks,
        )

    def export_clip(
        self,
        source: Path,
        destination: Path,
        *,
        start_seconds: float,
        duration_seconds: float,
        cancel_event: threading.Event | None = None,
        runner=subprocess.run,
    ) -> None:
        _admit_local_decode_path(source)
        source = source.resolve()
        destination = destination.resolve()
        command = [
            self.ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-protocol_whitelist",
            "file,pipe",
            "-threads",
            str(self.threads),
            "-y",
            "-ss",
            f"{start_seconds:.3f}",
            "-i",
            str(source),
            "-t",
            f"{duration_seconds:.3f}",
            "-c",
            "copy",
            str(destination),
        ]
        decision = constrained_decoder(argv=command, network_enabled=False, settings=self.settings)
        if not decision["admitted"]:
            raise ValueError("unconstrained decoder")
        _assert_safe_ffmpeg_argv(command, settings=self.settings)
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError("ffmpeg export cancelled")
        if runner is subprocess.run:
            _run_bounded_media_process(
                command,
                timeout=120,
                output_cap=4 * 1024**2,
                file_cap=self.max_output_bytes,
                cancel_event=cancel_event,
            )
        else:
            runner(command, check=True, capture_output=True, timeout=120)
        if destination.stat().st_size > self.max_output_bytes:
            destination.unlink(missing_ok=True)
            raise MediaResourceLimit("ffmpeg export exceeded output-byte cap")


def _assert_safe_ffmpeg_argv(command: list[str], *, settings=None) -> None:
    if not command:
        raise ValueError("refusing unexpected media binary")
    name = Path(command[0]).name.removesuffix(".exe")
    if name not in {"ffmpeg", "ffprobe"}:
        raise ValueError("refusing unexpected media binary")
    resolved = resolve_trusted_executable(
        name,  # type: ignore[arg-type]
        configured=command[0] if Path(command[0]).is_absolute() else None,
        settings=settings,
    )
    if Path(command[0]) != resolved:
        raise ValueError("refusing unresolved media binary")
    joined = shlex.join(command)
    if any(token in joined for token in ("`", "$(", ";", "|", "&&", "\n")):
        raise ValueError("refusing unsafe ffmpeg arguments")


def _admit_local_decode_path(path: Path) -> None:
    raw = str(path).replace("\\", "/")
    lowered = raw.lower()
    if any(token in lowered for token in ("http:", "https:", "rtsp:", "rtmp:", "ftp:")):
        raise ValueError("unconstrained decoder")
    if "://" in raw and not lowered.startswith("file:"):
        raise ValueError("unconstrained decoder")


def _opencv_presentation_clock(
    capture: object,
    cv2_module: object,
    index: int,
    *,
    last_msec: float | None = None,
) -> tuple[float | None, int | None, Literal["decoder_pts", "missing"]]:
    del index
    msec_prop = getattr(cv2_module, "CAP_PROP_POS_MSEC", 0)
    try:
        msec = float(capture.get(msec_prop) or 0.0)  # type: ignore[attr-defined]
    except Exception:
        msec = 0.0
    if last_msec is not None and msec <= last_msec + 1e-6:
        return None, None, "missing"
    return msec / 1000.0, int(round(msec)), "decoder_pts"


def export_timestamp_seconds(*, presentation_time_seconds: float | None, frame_count: int, fps: float) -> float:
    """Prefer decoder PTS. Index/fps is only a last-resort label, never treated as VFR identity."""

    if presentation_time_seconds is not None:
        return float(presentation_time_seconds)
    return frame_count / (fps or 1.0)


def should_export_on_source_grid(
    presentation_time_seconds: float | None,
    *,
    frame_count: int,
    frame_interval: int,
    last_export_presentation_time: float | None,
    grid_step_seconds: float,
    grid_origin_presentation_time: float | None = None,
    pts: int | None = None,
    time_base: tuple[int, int] | None = None,
    last_export_pts: int | None = None,
    grid_origin_pts: int | None = None,
    target_fps: float | None = None,
) -> bool:
    """Export on a source-time grid. Index modulo is only used when PTS is missing."""

    if (
        pts is not None
        and time_base is not None
        and target_fps
        and target_fps > 0
        and (last_export_pts is not None or last_export_presentation_time is None)
    ):
        if last_export_pts is None:
            return True
        numerator, denominator = time_base
        if numerator <= 0 or denominator <= 0:
            raise ValueError("time base must be positive")
        origin = pts if grid_origin_pts is None else grid_origin_pts
        step = Fraction(denominator, numerator) / Fraction(str(target_fps))
        completed_steps = (Fraction(last_export_pts - origin, 1) / step).__floor__()
        return Fraction(pts - origin, 1) >= (completed_steps + 1) * step
    if presentation_time_seconds is None:
        return frame_count % max(int(frame_interval), 1) == 0
    if last_export_presentation_time is None:
        return True
    step = float(grid_step_seconds) if grid_step_seconds > 0 else 0.0
    if step <= 0:
        return True
    if grid_origin_presentation_time is None:
        threshold = float(last_export_presentation_time) + step
    else:
        origin = float(grid_origin_presentation_time)
        completed_steps = int(
            (float(last_export_presentation_time) - origin + 1e-9) // step
        )
        threshold = origin + (completed_steps + 1) * step
    return float(presentation_time_seconds) + 1e-9 >= threshold


def presentation_seconds_or_none(decoded: object) -> float | None:
    if getattr(decoded, "presentation_clock", "decoder_pts") == "missing":
        return None
    value = getattr(decoded, "presentation_time_seconds", None)
    if value is None:
        return None
    return float(value)


def should_sample_on_source_grid(
    decoded: object,
    *,
    frame_count: int,
    frame_interval: int,
    last_sample_presentation_time: float | None,
    fps: float | None,
    grid_origin_presentation_time: float | None = None,
    last_sample_pts: int | None = None,
    grid_origin_pts: int | None = None,
) -> bool:
    """Sample recovery/player windows on the PTS grid when a decoder clock exists."""

    presentation = presentation_seconds_or_none(decoded)
    if presentation is None or fps is None or float(fps) <= 0:
        return frame_count % max(int(frame_interval), 1) == 0
    return should_export_on_source_grid(
        presentation,
        frame_count=frame_count,
        frame_interval=frame_interval,
        last_export_presentation_time=last_sample_presentation_time,
        grid_step_seconds=float(frame_interval) / float(fps),
        grid_origin_presentation_time=grid_origin_presentation_time,
        pts=getattr(decoded, "pts", None),
        time_base=getattr(decoded, "time_base", None),
        last_export_pts=last_sample_pts,
        grid_origin_pts=grid_origin_pts,
        target_fps=float(fps) / max(int(frame_interval), 1),
    )


def run_proxy_ffmpeg_job(
    original: Path,
    destination: Path,
    *,
    original_sha256: str,
    proxy_height: int = 720,
    runner=None,
    hash_cache: HashCache | None = None,
) -> dict[str, object]:
    digest = _file_identity(original, hash_cache).sha256
    if digest != original_sha256:
        raise ValueError("original digest mismatch; refusing to replace the source asset")
    command = [
        str(resolve_trusted_executable("ffmpeg")),
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(original),
        "-vf",
        f"scale=-2:{int(proxy_height)}",
        "-an",
        "-y",
        str(destination),
    ]
    decision = constrained_decoder(argv=command, network_enabled=False)
    if not decision["admitted"]:
        raise ValueError("unconstrained decoder")
    _assert_safe_ffmpeg_argv(command)
    execute = runner or subprocess.run
    execute(command, check=True, capture_output=True, timeout=120)
    return derive_proxy_assets(
        original,
        original_sha256=original_sha256,
        original_pts=[0],
        time_base=(1, 1),
        proxy_height=proxy_height,
        hash_cache=hash_cache,
    )


def _parse_rate(value: str) -> tuple[int, int]:
    if "/" not in value:
        return (int(float(value)), 1) if value not in {"", "N/A"} else (0, 1)
    num, den = value.split("/", 1)
    return int(num or 0), int(den or 1)


def _is_vfr(video: dict) -> bool:
    avg = video.get("avg_frame_rate")
    r = video.get("r_frame_rate")
    return bool(avg and r and avg != r)


def _rotation_from_tags(video: dict) -> int:
    tags = video.get("tags") or {}
    try:
        return int(float(tags.get("rotate") or 0))
    except (TypeError, ValueError):
        return 0


@dataclass
class SamplingAudit:
    """Count decode, inference, tracker and export rates independently (GA-15)."""

    source_sha256: str
    declared_target_fps: float
    nominal_fps: float | None
    frame_interval: int
    selected_backend: str
    temporal_policy: str = "source_global_grid"
    fallback_backend: str | None = None
    decoded_frame_count: int = 0
    primary_inference_count: int = 0
    recovery_inference_count: int = 0
    tracker_update_count: int = 0
    exported_sample_count: int = 0
    fallback_occurred: bool = False
    notes: list[str] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_decoded_frame(self) -> None:
        with self._lock:
            self.decoded_frame_count += 1

    def record_primary_inference(self) -> None:
        with self._lock:
            self.primary_inference_count += 1

    def record_recovery_inference(self) -> None:
        with self._lock:
            self.recovery_inference_count += 1

    def record_tracker_update(self) -> None:
        with self._lock:
            self.tracker_update_count += 1

    def record_export_sample(self) -> None:
        with self._lock:
            self.exported_sample_count += 1

    def record_fallback(self, backend: str) -> None:
        with self._lock:
            self.fallback_occurred = True
            self.fallback_backend = backend
            self.notes.append(f"fell_back_to:{backend}")

    def receipt(self) -> SamplingReceipt:
        notes = list(self.notes)
        if self.exported_sample_count != self.primary_inference_count:
            notes.append("EXPORT_FPS_IS_NOT_INFERENCE_FPS")
        return SamplingReceipt(
            sourceSha256=self.source_sha256,
            declaredTargetFps=self.declared_target_fps,
            nominalFps=self.nominal_fps,
            frameInterval=self.frame_interval,
            decodedFrameCount=self.decoded_frame_count,
            primaryInferenceCount=self.primary_inference_count,
            recoveryInferenceCount=self.recovery_inference_count,
            trackerUpdateCount=self.tracker_update_count,
            exportedSampleCount=self.exported_sample_count,
            temporalPolicy=self.temporal_policy,
            selectedBackend=self.selected_backend,
            fallbackBackend=self.fallback_backend,
            fallbackOccurred=self.fallback_occurred,
            notes=notes,
        )

    def four_rates(self) -> FourRatesReceipt:
        return four_rates_receipt(self)


def frame_interval_for_target_fps(nominal_fps: float, target_fps: float) -> int:
    if nominal_fps <= 0 or target_fps <= 0:
        return 1
    return int(nominal_fps / target_fps) if nominal_fps > target_fps else 1


def pts_to_seconds(pts: int, time_base_num: int, time_base_den: int) -> float:
    if time_base_den == 0:
        raise ValueError("invalid time base")
    return (pts * time_base_num) / time_base_den


def align_clip_start_to_grid(
    *,
    clip_start_source_frame: int,
    evaluation_step: int,
) -> dict[str, int | bool | str]:
    """Preserve source-global evaluation alignment. Do not renumber source frames."""

    remainder = clip_start_source_frame % evaluation_step
    aligned = remainder == 0
    return {
        "clipStartSourceFrame": clip_start_source_frame,
        "evaluationStep": evaluation_step,
        "onGrid": aligned,
        "remainder": remainder,
        "policy": "source_global_grid",
    }


def map_decoded_to_sample(
    frame: DecodedFrame,
    *,
    frame_interval: int,
    match_clock_offset_seconds: float = 0.0,
) -> FrameIdentity | None:
    if frame_interval <= 0:
        raise ValueError("frame_interval must be positive")
    exported = frame.source_frame_index % frame_interval == 0
    if not exported:
        return None
    return FrameIdentity(
        sourceFrameIndex=frame.source_frame_index,
        presentationTimeSeconds=frame.presentation_time_seconds,
        pts=frame.pts,
        sampleId=f"{frame.backend}:{frame.source_frame_index}",
        matchClockSeconds=frame.presentation_time_seconds + match_clock_offset_seconds,
        decoderBackend=frame.backend,
        pixelFormat="bgr24" if frame.colour_order == "bgr" else "rgb24",
    )


def detect_camera_cuts(presentation_times: list[float], *, jump_seconds: float = 0.5) -> list[int]:
    cuts: list[int] = []
    for index in range(1, len(presentation_times)):
        delta = presentation_times[index] - presentation_times[index - 1]
        if delta < 0 or delta > jump_seconds:
            cuts.append(index)
    return cuts


def sample_decode_anchors(frames: list[DecodedFrame]) -> dict[str, object]:
    if not frames:
        return {"beginning": None, "middle": None, "end": None, "discontinuities": []}
    times = [frame.presentation_time_seconds for frame in frames]
    return {
        "beginning": times[0],
        "middle": times[len(times) // 2],
        "end": times[-1],
        "discontinuities": detect_camera_cuts(times),
    }


def apply_crop_and_rotation(
    width: int,
    height: int,
    *,
    crop: tuple[int, int, int, int] | None,
    rotation: int,
    colour_order: ColourOrder,
) -> dict[str, object]:
    x, y, w, h = crop or (0, 0, width, height)
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height:
        raise ValueError("crop is outside the source frame")
    if rotation % 90 != 0:
        raise ValueError("rotation must be a multiple of 90 degrees")
    out_w, out_h = (h, w) if rotation % 180 else (w, h)
    return {
        "width": out_w,
        "height": out_h,
        "colourOrder": colour_order,
        "rotation": rotation % 360,
        "crop": [x, y, w, h],
    }


def cpu_fallback(selected: str, available: set[str]) -> str:
    if selected in available:
        return selected
    if "opencv" in available:
        return "opencv"
    if "fixture" in available:
        return "fixture"
    raise RuntimeError("no CPU decode fallback is available")


def decode_memory_policy(
    *,
    mode: str,
    hardware_decode_ok: bool,
    cuda_visible: bool,
    drop_policy: str | None = None,
    video_engine_capability: bool = False,
) -> dict[str, object]:
    """4.5B: bound queues, backpressure, and fail-closed GPU residency."""
    del cuda_visible, video_engine_capability
    gpu_capable = bool(hardware_decode_ok)
    reasons = [] if gpu_capable else ["HW_DECODE_UNAVAILABLE"]
    live = mode == "live"
    declared_drop = live and drop_policy == "declared"
    return {
        "retainAllDecodedFrames": False,
        "backpressure": mode == "offline",
        "reportsMissingSourceEvidence": mode == "offline",
        "gpuResident": False,
        "zeroCopy": False,
        "canPromoteDefault": False,
        "mayDrop": declared_drop,
        "dropPolicy": drop_policy if declared_drop else None,
        "reasonCodes": reasons,
        "videoEngineCapability": gpu_capable,
    }


class PyAvFrameSource(FrameSource):
    """4.5A CPU decoder challenger. Never the production default."""

    name = "pyav"

    def probe(self, path: Path) -> SourceClockIdentity:
        del path
        raise RuntimeError("pyav is a challenger, not a default decoder")

    def iter_frames(self, path: Path, *, cancel_event: threading.Event | None = None) -> Iterator[DecodedFrame]:
        del path, cancel_event
        raise RuntimeError("pyav is not a default decoder")


class TorchCodecFrameSource(FrameSource):
    """4.5A tensor decoder challenger. Never the production default."""

    name = "torchcodec"

    def probe(self, path: Path) -> SourceClockIdentity:
        del path
        raise RuntimeError("torchcodec is a challenger, not a default decoder")

    def iter_frames(self, path: Path, *, cancel_event: threading.Event | None = None) -> Iterator[DecodedFrame]:
        del path, cancel_event
        raise RuntimeError("torchcodec is not a default decoder")


@dataclass(frozen=True)
class FourRatesReceipt:
    """Four rates, one source clock. Export fps is never inference fps."""

    decodeCount: int
    detectorPrimaryCount: int
    detectorRecoveryCount: int
    trackerUpdateCount: int
    exportCount: int
    exportFpsEqualsInferenceFps: bool = False
    decodeFpsEqualsExportFps: bool = False
    notes: tuple[str, ...] = ()


def four_rates_receipt(audit: SamplingAudit) -> FourRatesReceipt:
    notes = list(audit.notes)
    if audit.exported_sample_count != audit.primary_inference_count:
        notes.append("EXPORT_FPS_IS_NOT_INFERENCE_FPS")
    return FourRatesReceipt(
        decodeCount=audit.decoded_frame_count,
        detectorPrimaryCount=audit.primary_inference_count,
        detectorRecoveryCount=audit.recovery_inference_count,
        trackerUpdateCount=audit.tracker_update_count,
        exportCount=audit.exported_sample_count,
        exportFpsEqualsInferenceFps=False,
        decodeFpsEqualsExportFps=False,
        notes=tuple(notes),
    )


def vid_stride_policy() -> dict[str, bool]:
    """Do not add vid_stride alone. TARGET_FPS is not an inference-rate limit."""

    return {
        "addsVidStrideAlone": False,
        "targetFpsEqualsInferenceFps": False,
        "explicitFrameContractRequired": True,
        "oldEvidenceCompatible": True,
    }


def map_original_to_proxy_pts(
    *,
    original_pts: list[int],
    proxy_pts: list[int],
    time_base: tuple[int, int],
) -> list[dict[str, int | float]]:
    num, den = time_base
    mapping: list[dict[str, int | float]] = []
    for original, proxy in zip(original_pts, proxy_pts, strict=True):
        mapping.append(
            {
                "originalPts": original,
                "proxyPts": proxy,
                "originalSeconds": pts_to_seconds(original, num, den),
                "proxySeconds": pts_to_seconds(proxy, num, den),
            }
        )
    return mapping


def resolve_declared_interval(
    kind: str,
    start_seconds: float,
    end_seconds: float,
    mapping: list[dict[str, int | float]],
) -> tuple[float, float]:
    del kind, mapping
    return (start_seconds, end_seconds)


def derive_proxy_assets(
    original: Path,
    *,
    original_sha256: str,
    original_pts: list[int],
    time_base: tuple[int, int],
    proxy_height: int = 720,
    hash_cache: HashCache | None = None,
) -> dict[str, object]:
    digest = _file_identity(original, hash_cache).sha256
    if digest != original_sha256:
        raise ValueError("original digest mismatch; refusing to replace the source asset")
    mapping = map_original_to_proxy_pts(original_pts=original_pts, proxy_pts=list(original_pts), time_base=time_base)
    return {
        "replacesOriginal": False,
        "originalRetained": True,
        "originalSha256": digest,
        "assets": {
            "proxy": {"kind": "browsing_proxy", "height": proxy_height, "streamCopy": True},
            "thumbnails": {"kind": "thumbnails", "count": max(1, len(original_pts))},
            "waveform": {"kind": "waveform"},
        },
        "ptsMap": mapping,
        "frameExactExport": {"validatedDecodeReencode": True, "keyframeSeekIsExact": False},
    }


def store_edit_list(*, source_sha256: str, intervals: list[dict[str, float]]) -> dict[str, object]:
    return {
        "sourceSha256": source_sha256,
        "intervals": [(float(item["start"]), float(item["end"])) for item in intervals],
        "reencodeFullMatch": False,
        "renderOnDemand": True,
    }


def render_on_demand(edit_list: dict[str, object], *, start: float, end: float) -> dict[str, object]:
    return {
        "sourceSha256": edit_list["sourceSha256"],
        "interval": (start, end),
        "reencodedFullMatch": False,
    }


def torso_colour_pixels(pixels: bytes, *, colour_order: ColourOrder, convert: bool = True) -> bytes:
    if colour_order == "rgb":
        if not convert:
            raise ValueError("rgb decoder without conversion would change team-colour evidence")
        swapped = bytearray()
        for index in range(0, len(pixels), 3):
            red, green, blue = pixels[index : index + 3]
            swapped.extend((blue, green, red))
        return bytes(swapped)
    return pixels


def colour_round_trip(
    *,
    source_box: tuple[int, int, int, int],
    crop: tuple[int, int, int, int],
    rotation: int,
) -> tuple[int, int, int, int]:
    del crop
    if rotation % 360 != 0:
        raise ValueError("non-zero rotation must be inverted before publishing source boxes")
    return source_box
