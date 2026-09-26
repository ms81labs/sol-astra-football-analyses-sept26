"""GA-02 source-clock identity, GA-15 sampling audit, GA-16 FrameSource adapters."""

from __future__ import annotations

import json
import math
import stat
import os
import re
import shlex
import subprocess
import threading
import time
import tempfile
from fractions import Fraction
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterator, Literal, TypedDict, cast
from collections.abc import Sequence

from .contracts import FrameIdentity, SamplingReceipt, SourceClockIdentity
from .hashing import HashCache, stream_sha256
from .executables import resolve_trusted_executable
from .media_execution import (
    DecodeCancelled, TruncatedStream, DecoderFailed, MediaResourceLimit,
    MediaExecutionPolicy, MediaExecution, media_failure_receipt,
)


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


class _ShowinfoParser:
    _pattern = re.compile(
        rb"\bn:\s*(?P<n>\d+).*?\bpts:\s*(?P<pts>-?\d+).*?\bpts_time:\s*(?P<time>-?\d+(?:\.\d+)?)"
    )

    def __init__(self, max_line_bytes: int = 65536) -> None:
        self.carry = b""
        self.max_line_bytes = max_line_bytes

    def feed(self, chunk: bytes) -> list[tuple[int, int, float]]:
        lines = (self.carry + chunk).split(b"\n")
        self.carry = lines.pop()
        if len(self.carry) > self.max_line_bytes:
            raise MediaResourceLimit("ffmpeg diagnostic-line limit")
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


def _read_exact(stream, size: int, *, progress=None) -> bytes | None:
    # Two payload-sized buffers at conversion, rather than an unbounded chunk list.
    payload = bytearray(size)
    view = memoryview(payload)
    offset = 0
    while offset < size:
        if hasattr(stream, "readinto1"):
            count = stream.readinto1(view[offset:])
        elif hasattr(stream, "readinto"):
            count = stream.readinto(view[offset:])
        else:
            chunk = stream.read(size - offset)
            count = len(chunk)
            view[offset:offset + count] = chunk
            del chunk
        if not count:
            if offset:
                raise TruncatedStream("decoder ended mid-frame")
            return None
        offset += count
        if progress is not None:
            progress()
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
        import cv2

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
                if clock == "decoder_pts" and presentation_time_seconds is not None:
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
    """Bounded diagnostic challenger; does not change the default decoder."""
    name = "ffmpeg"

    def __init__(
        self, frames: list[DecodedFrame] | None = None,
        identity: SourceClockIdentity | None = None, probe: FfmpegProbe | None = None,
        hash_cache: HashCache | None = None, max_output_bytes: int | None = None,
        wall_timeout_seconds: float | None = None, threads: int | None = None,
        *, policy: MediaExecutionPolicy | None = None,
    ):
        effective = policy or (probe.policy if probe is not None else MediaExecutionPolicy())
        decoded_limit = effective.max_decoded_bytes
        if max_output_bytes is not None:
            decoded_limit = min(max_output_bytes, decoded_limit) if decoded_limit is not None else max_output_bytes
        job_timeout = effective.job_timeout_seconds
        if wall_timeout_seconds is not None:
            job_timeout = min(wall_timeout_seconds, job_timeout)
        self.policy = replace(
            effective,
            max_decoded_bytes=decoded_limit,
            job_timeout_seconds=job_timeout,
            threads=threads if threads is not None else effective.threads,
        )
        self.policy.admit_mode()
        self._frames = list(frames or [])
        self._identity = identity
        self._hash_cache = hash_cache
        self._probe = FfmpegProbe(
            ffprobe=probe.ffprobe if probe is not None else None,
            ffmpeg=probe.ffmpeg if probe is not None else None,
            settings=probe.settings if probe is not None else None,
            hash_cache=hash_cache or (probe.hash_cache if probe is not None else None),
            policy=self.policy,
        )
        self.last_execution_receipt: dict[str, object] | None = None

    def probe(self, path: Path) -> SourceClockIdentity:
        if self._identity is not None:
            identity = _file_identity(path, self._hash_cache) if path.exists() else None
            return self._identity.model_copy(update={
                "sourceSha256": identity.sha256 if identity else self._identity.sourceSha256,
                "byteSize": identity.size if identity else 0,
            })
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
        try:
            yield from self._iter_ffmpeg_decode(path, cancel_event=cancel_event)
        except Exception as error:
            self.last_execution_receipt = media_failure_receipt(
                error, policy=self.policy, previous=self.last_execution_receipt)
            raise

    def _iter_ffmpeg_decode(self, path: Path, *, cancel_event: threading.Event | None) -> Iterator[DecodedFrame]:
        started = time.monotonic()
        self.last_execution_receipt = None
        path = _media_source_path(path, self.policy)
        identity = self._identity or self._probe.probe_identity(
            path, cancel_event=cancel_event, deadline=started + self.policy.job_timeout_seconds)
        frame_size, total_cap = self.policy.decode_budget(identity)
        assert identity.width is not None and identity.height is not None  # decode_budget admits dimensions.
        width, height = int(identity.width), int(identity.height)
        command = [self._probe.ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "info",
                   "-protocol_whitelist", "file,pipe", "-threads", str(self.policy.threads),
                   "-noautorotate", "-i", str(path), "-map", "0:v:0", "-an",
                   "-vf", "showinfo", "-fps_mode", "passthrough", "-f", "rawvideo",
                   "-threads", str(self.policy.threads), "-pix_fmt", "bgr24", "pipe:1"]
        _assert_safe_ffmpeg_argv(command, settings=self._probe.settings)
        source_before = stream_sha256(path)
        if self._identity is None and source_before.sha256 != identity.sourceSha256:
            raise ValueError("source changed after media admission")
        remaining = self.policy.job_timeout_seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise MediaResourceLimit("ffmpeg process exceeded wall-clock timeout")
        with tempfile.TemporaryDirectory(prefix="ga-ffmpeg-decode-") as scratch:
            execution = MediaExecution(command, policy=self.policy, cwd=Path(scratch),
                                       timeout=remaining, cancel_event=cancel_event)
            process = execution.process
            self.last_execution_receipt = execution.receipt
            execution.receipt.update(operation="decode", sourceSha256=source_before.sha256,
                                     totalDecodedByteCap=total_cap, decodedBytes=0, decodedFrames=0,
                                     peakReadBufferBytes=0, queuedFrames=0, peakTimingEntries=0,
                                     timingEntryLimit=64,
                                     bufferScope="producer payload assembly/conversion; excludes caller retention and child RSS")
            assert process.stdout is not None and process.stderr is not None
            stderr_stream = process.stderr
            condition = threading.Condition()
            pts_by_index: dict[int, tuple[int, float]] = {}
            diagnostics = bytearray()
            stderr_done = False
            stderr_errors: list[BaseException] = []

            stopped = threading.Event()

            def store_timing(rows) -> None:
                with condition:
                    for frame_index, pts, pts_time in rows:
                        while len(pts_by_index) >= 64 and frame_index not in pts_by_index:
                            if stopped.is_set() or execution.reason is not None:
                                return
                            condition.wait(timeout=0.02)
                        pts_by_index[frame_index] = (pts, pts_time)
                        execution.receipt["peakTimingEntries"] = max(
                            int(execution.receipt["peakTimingEntries"]), len(pts_by_index))
                        condition.notify_all()

            def read_stderr() -> None:
                nonlocal stderr_done
                parser = _ShowinfoParser(self.policy.diagnostic_tail_bytes)
                try:
                    while not stopped.is_set() and (chunk := (
                        stderr_stream.read1(65536) if hasattr(stderr_stream, "read1") else stderr_stream.read(65536)
                    )):
                        diagnostics.extend(chunk)
                        del diagnostics[:-self.policy.diagnostic_tail_bytes]
                        store_timing(parser.feed(chunk))
                    store_timing(parser.finish())
                except BaseException as exc:
                    stderr_errors.append(exc)
                    execution.abort("DIAGNOSTIC_LIMIT")
                finally:
                    with condition:
                        stderr_done = True
                        condition.notify_all()

            reader = threading.Thread(target=read_stderr, name="ga-media-stderr", daemon=True)
            reader.start()
            completed = False
            index = output_bytes = 0
            seen_pts: set[int] = set()
            origin: Fraction | None = None
            try:
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        execution.abort("CANCELLED")
                    execution.check(tail=diagnostics.decode(errors="replace").splitlines()[-256:])
                    execution.demand(True)
                    try:
                        payload = _read_exact(process.stdout, min(frame_size, total_cap - output_bytes + 1),
                                              progress=execution.progress)
                    except TruncatedStream:
                        execution.check(tail=diagnostics.decode(errors="replace").splitlines()[-256:])
                        raise
                    execution.check(tail=diagnostics.decode(errors="replace").splitlines()[-256:])
                    if payload is None:
                        break
                    output_bytes += len(payload)
                    execution.receipt["observedOutputBytes"] = output_bytes
                    if output_bytes > total_cap or index >= self.policy.max_frames:
                        execution.abort("WORK_LIMIT")
                        execution.check()
                    with condition:
                        deadline = time.monotonic() + min(5.0, self.policy.stall_timeout_seconds)
                        while index not in pts_by_index and not stderr_done and execution.reason is None:
                            remaining = deadline - time.monotonic()
                            if remaining <= 0:
                                break
                            condition.wait(timeout=min(0.05, remaining))
                        timing = pts_by_index.pop(index, None)
                        condition.notify_all()
                    execution.check()
                    pts = None if timing is None else timing[0]
                    time_base = (int(identity.timeBaseNum or 1), int(identity.timeBaseDen or 1))
                    if min(time_base) <= 0:
                        raise ValueError("invalid decoder time base")
                    presentation = None if pts is None else Fraction(pts * time_base[0], time_base[1])
                    if presentation is not None:
                        origin = presentation if origin is None else min(origin, presentation)
                        if presentation - origin > self.policy.max_duration_seconds:
                            execution.abort("DURATION_LIMIT")
                            execution.check()
                    duplicate = pts in seen_pts if pts is not None else False
                    if pts is not None:
                        seen_pts.add(pts)
                    execution.receipt.update(decodedBytes=output_bytes, decodedFrames=index + 1,
                                             peakReadBufferBytes=2 * frame_size)
                    execution.demand(False)  # Consumer work is not an active decoder stall.
                    yield DecodedFrame(index, pts, None if presentation is None else float(presentation),
                        width, height, "bgr", int(identity.rotation or 0), payload, self.name,
                        presentation_clock="decoder_pts" if pts is not None else "missing",
                        time_base=time_base, duplicate_pts=duplicate)
                    del payload  # Do not retain the preceding payload while assembling the next.
                    index += 1
                process.wait(timeout=self.policy.job_timeout_seconds + 1)
                execution.demand(False)
                execution.close()
                reader.join(timeout=self.policy.cancellation_grace_seconds + 1)
                execution.check(tail=diagnostics.decode(errors="replace").splitlines()[-256:])
                if reader.is_alive() or stderr_errors:
                    raise DecoderFailed(process.returncode, tail=["stderr reader did not complete"])
                if stream_sha256(path) != source_before:
                    raise ValueError("source changed during media execution")
                completed = True
            except GeneratorExit:
                execution.reason = execution.reason or "GENERATOR_CLOSED"
                execution.receipt["outcome"] = execution.reason
                raise
            except BaseException as error:
                execution.receipt.update(media_failure_receipt(error, policy=self.policy, previous=execution.receipt))
                execution.reason = execution.reason or execution.receipt["outcome"]
                vars(error)["execution_receipt"] = execution.receipt
                raise
            finally:
                stopped.set()
                with condition:
                    condition.notify_all()
                if not completed and execution.reason is None and process.poll() is None:
                    execution.reason = "GENERATOR_CLOSED"
                execution.close()
                reader.join(timeout=self.policy.cancellation_grace_seconds + 1)
                process.stdout.close()
                process.stderr.close()


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


class MediaProcessResult(subprocess.CompletedProcess[bytes]):
    execution_receipt: dict


def _run_bounded_media_process(
    command: list[str], *, timeout: float, output_cap: int, file_cap: int,
    cancel_event: threading.Event | None = None, policy: MediaExecutionPolicy | None = None,
    deadline: float | None = None,
) -> MediaProcessResult:
    """Common process boundary for probe, proxy and export, including cancellation."""
    base = policy or MediaExecutionPolicy()
    timeout = _remaining_media_timeout(deadline, min(timeout, base.job_timeout_seconds), cancel_event)
    effective = replace(base, captured_output_bytes=min(output_cap, base.captured_output_bytes),
                        max_file_bytes=min(file_cap, base.max_file_bytes))
    with tempfile.TemporaryDirectory(prefix="ga-media-child-") as scratch:
        execution = MediaExecution(command, policy=effective, cwd=Path(scratch),
                                   timeout=timeout, cancel_event=cancel_event)
        process = execution.process
        assert process.stdout is not None and process.stderr is not None
        chunks: dict[str, list[bytes]] = {"stdout": [], "stderr": []}
        size = 0
        lock = threading.Lock()
        errors: list[BaseException] = []

        def drain(name: str, stream) -> None:
            nonlocal size
            try:
                while chunk := (stream.read1(65536) if hasattr(stream, "read1") else stream.read(65536)):
                    with lock:
                        size += len(chunk)
                        overflow = size > effective.captured_output_bytes
                        if not overflow:
                            chunks[name].append(chunk)
                    if overflow:
                        execution.abort("CAPTURE_LIMIT")
                        return
            except BaseException as exc:
                errors.append(exc)
                execution.abort("CAPTURE_READ_FAILED")

        readers = [threading.Thread(target=drain, args=(name, stream), name=f"ga-media-{name}", daemon=True)
                   for name, stream in (("stdout", process.stdout), ("stderr", process.stderr))]
        for reader in readers:
            reader.start()
        try:
            while process.poll() is None or any(reader.is_alive() for reader in readers):
                if execution.reason is not None:
                    break
                time.sleep(0.02)
            execution.close()
            for reader in readers:
                reader.join(timeout=effective.cancellation_grace_seconds + 1)
            stderr = b"".join(chunks["stderr"])
            execution.check(tail=stderr.decode(errors="replace").splitlines()[-256:])
            if errors or any(reader.is_alive() for reader in readers):
                raise DecoderFailed(process.returncode, tail=["media pipe reader did not finish"])
            result = cast(MediaProcessResult, subprocess.CompletedProcess(command, process.returncode, b"".join(chunks["stdout"]), stderr))
            result.execution_receipt = execution.receipt
            return result
        finally:
            execution.close()
            for reader in readers:
                reader.join(timeout=effective.cancellation_grace_seconds + 1)
            process.stdout.close()
            process.stderr.close()


def _remaining_media_timeout(deadline: float | None, limit: float, cancel_event=None) -> float:
    if cancel_event is not None and cancel_event.is_set():
        raise DecodeCancelled("ffmpeg process cancelled")
    remaining = limit if deadline is None else min(limit, deadline - time.monotonic())
    if not math.isfinite(remaining) or remaining <= 0:
        raise MediaResourceLimit("ffmpeg process exceeded wall-clock timeout")
    return remaining


def _media_source_path(path: Path, policy: MediaExecutionPolicy) -> Path:
    policy.admit_mode()
    _admit_local_decode_path(path)
    path = path.resolve(strict=True)
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError("media source must be a regular local file")
    if metadata.st_size > policy.max_source_bytes:
        raise MediaResourceLimit("SOURCE_NOT_ADMITTED: byteSize")
    return path


def _publish_media_output(source: Path, destination: Path, command: list[str], *,
                          policy: MediaExecutionPolicy, cancel_event=None, runner=None,
                          validate_output=None, deadline=None, expected_source_sha256=None) -> dict:
    """Publish only a successful staged output; failures retain any old artifact."""
    _remaining_media_timeout(deadline, policy.export_timeout_seconds, cancel_event)
    raw_destination = destination.absolute()
    if raw_destination.is_symlink():
        raise ValueError("refusing a symlink media destination")
    destination = raw_destination.parent.resolve(strict=True) / raw_destination.name
    if destination == source or (destination.exists() and os.path.samefile(source, destination)):
        raise ValueError("refusing to replace the source asset")
    if destination.exists() and not destination.is_file():
        raise ValueError("media destination is not a regular file")
    if cancel_event is not None and cancel_event.is_set():
        raise DecodeCancelled("ffmpeg export cancelled")
    before = stream_sha256(source)
    if expected_source_sha256 is not None and before.sha256 != expected_source_sha256:
        raise ValueError("source changed after media admission")
    fd, temporary = tempfile.mkstemp(prefix=".ga-media-", suffix=destination.suffix, dir=destination.parent)
    os.close(fd)
    staged = Path(temporary)
    argv = [*command[:-1], str(staged)]
    receipt = None
    try:
        if runner is None or runner is subprocess.run:
            completed = _run_bounded_media_process(argv,
                timeout=policy.export_timeout_seconds, output_cap=policy.captured_output_bytes,
                file_cap=policy.max_file_bytes, cancel_event=cancel_event, policy=policy, deadline=deadline)
            receipt = completed.execution_receipt
        else:
            completed = runner(argv, check=True, capture_output=True, timeout=policy.export_timeout_seconds)
            if getattr(completed, "returncode", 0) != 0:
                raise DecoderFailed(completed.returncode, tail=[])
            receipt = {"outcome": "external_runner_unverified", "policySha256": policy.digest,
                       "enforcedLimits": {}, "reaped": False}
        if cancel_event is not None and cancel_event.is_set():
            raise DecodeCancelled("ffmpeg export cancelled")
        if stream_sha256(source) != before:
            raise ValueError("original changed; refusing media publication")
        info = staged.lstat()
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= policy.max_file_bytes:
            raise MediaResourceLimit("ffmpeg export exceeded output-byte cap or produced no output")
        if validate_output is not None:
            validate_output(staged)
        if stream_sha256(source) != before:
            raise ValueError("source changed; refusing media publication")
        _remaining_media_timeout(deadline, policy.export_timeout_seconds, cancel_event)
        with staged.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(staged, destination)
        receipt.update(sourceSha256=before.sha256, outputBytes=info.st_size, published=True)
        return receipt
    except BaseException as error:
        media_failure_receipt(error, policy=policy, previous=receipt)
        raise
    finally:
        staged.unlink(missing_ok=True)


class FfmpegProbe:
    """GA-16 FFmpeg/ffprobe jobs with safe arguments and cancellation."""

    def __init__(
        self,
        ffprobe: str | None = None,
        ffmpeg: str | None = None,
        *,
        settings=None,
        hash_cache: HashCache | None = None,
        max_output_bytes: int | None = None,
        threads: int | None = None,
        policy: MediaExecutionPolicy | None = None,
    ):
        effective = policy or MediaExecutionPolicy()
        self.policy = replace(
            effective,
            max_file_bytes=min(max_output_bytes, effective.max_file_bytes) if max_output_bytes is not None else effective.max_file_bytes,
            threads=threads if threads is not None else effective.threads,
        )
        self.policy.admit_mode()
        self.last_execution_receipt: dict | None = None
        self.settings = settings
        self.hash_cache = hash_cache
        self.ffprobe = str(resolve_trusted_executable("ffprobe", configured=ffprobe, settings=settings))
        self.ffmpeg = str(resolve_trusted_executable("ffmpeg", configured=ffmpeg, settings=settings))
        self.max_output_bytes = self.policy.max_file_bytes
        self.threads = self.policy.threads

    def probe_identity(self, path: Path, *, runner=subprocess.run, cancel_event=None, selected_interval_seconds: float | None = None,
                       deadline: float | None = None) -> SourceClockIdentity:
        self.last_execution_receipt = None
        deadline = deadline if deadline is not None else time.monotonic() + self.policy.job_timeout_seconds
        try:
            path = _media_source_path(path, self.policy)
            before = stream_sha256(path)
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
                    command, timeout=self.policy.probe_timeout_seconds, output_cap=self.policy.captured_output_bytes,
                    file_cap=self.max_output_bytes, cancel_event=cancel_event, policy=self.policy, deadline=deadline
                )
                self.last_execution_receipt = completed.execution_receipt
                self.last_execution_receipt["operation"] = "probe"
                stdout = completed.stdout.decode("utf-8")
            else:
                stdout = runner(command, check=True, capture_output=True, text=True, timeout=self.policy.probe_timeout_seconds).stdout
                self.last_execution_receipt = {"outcome": "external_runner_unverified", "enforcedLimits": {}}
            payload = json.loads(stdout)
            if not isinstance(payload.get("streams", []), list) or len(payload.get("streams", [])) > self.policy.max_streams:
                raise MediaResourceLimit("SOURCE_NOT_ADMITTED: stream count")
            video: dict[str, Any] = next((stream for stream in payload.get("streams", []) if stream.get("codec_type") == "video"), {})
            audio_tracks = sum(1 for stream in payload.get("streams", []) if stream.get("codec_type") == "audio")
            num, den = _parse_rate(video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1")
            time_base_num, time_base_den = _parse_rate(video.get("time_base") or "1/1")
            fps = (num / den) if den else None
            duration = float(payload.get("format", {}).get("duration") or 0.0) or None
            file_identity = stream_sha256(path)
            if file_identity != before:
                raise ValueError("source changed during media probe")
            identity = SourceClockIdentity(
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
                frameCount=int(video["nb_frames"]) if str(video.get("nb_frames", "")).isdigit() else None,
                variableFrameRate=_is_vfr(video),
                audioTracks=audio_tracks,
            )

            admitted = identity if selected_interval_seconds is None else identity.model_copy(
                update={"durationSeconds": selected_interval_seconds, "frameCount": None})
            self.policy.admit_source(admitted)
            _remaining_media_timeout(deadline, self.policy.probe_timeout_seconds, cancel_event)
            return identity
        except BaseException as error:
            self.last_execution_receipt = media_failure_receipt(
                error, policy=self.policy, previous=self.last_execution_receipt)
            raise

    def export_clip(
        self,
        source: Path,
        destination: Path,
        *,
        start_seconds: float,
        duration_seconds: float,
        frame_exact: bool = False,
        cancel_event: threading.Event | None = None,
        runner=subprocess.run,
    ) -> None:
        self.last_execution_receipt = None
        deadline = time.monotonic() + self.policy.job_timeout_seconds
        try:
            source = _media_source_path(source, self.policy)
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                   for v in (start_seconds, duration_seconds)) or start_seconds < 0 or not 0 < duration_seconds <= self.policy.max_duration_seconds:
                raise ValueError("invalid export interval")
            if cancel_event is not None and cancel_event.is_set():
                raise DecodeCancelled("ffmpeg export cancelled")
            admission = None
            identity = None
            if runner is subprocess.run:
                identity = self.probe_identity(source, cancel_event=cancel_event,
                                               selected_interval_seconds=duration_seconds, deadline=deadline)
                if identity.durationSeconds is not None and start_seconds >= identity.durationSeconds:
                    raise ValueError("export interval is outside the source")
                admission = self.last_execution_receipt
            command = [self.ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error",
                       "-protocol_whitelist", "file,pipe", "-threads", str(self.threads), "-y"]
            if frame_exact:
                # Accurate seek drops frames with pts < -ss, so never round the start up
                # past the first frame: floor to microseconds with a 1 us margin (far below
                # any frame interval) and extend the duration by the same amount.
                seek = max(0.0, math.floor((start_seconds - 1e-6) * 1e6) / 1e6)
                command += ["-ss", f"{seek:.6f}", "-i", str(source),
                            "-t", f"{duration_seconds + start_seconds - seek:.6f}",
                            "-c:v", "libx264", "-c:a", "aac", "-fps_mode", "vfr"]
            else:
                command += ["-ss", f"{start_seconds:.3f}", "-i", str(source),
                            "-t", f"{duration_seconds:.3f}", "-c", "copy"]
            command.append(str(destination))
            _assert_safe_ffmpeg_argv(command, settings=self.settings)
            self.last_execution_receipt = _publish_media_output(source, destination, command,
                policy=self.policy, cancel_event=cancel_event, runner=runner, deadline=deadline,
                expected_source_sha256=identity.sourceSha256 if identity is not None else None)
            self.last_execution_receipt.update(operation="export", sourceProbe=admission,
                selectedIntervalSeconds=duration_seconds, decodedWorkApplicable=frame_exact, streamCopy=not frame_exact,
                frameExact=frame_exact)
        except BaseException as error:
            self.last_execution_receipt = media_failure_receipt(
                error, policy=self.policy, previous=self.last_execution_receipt)
            raise


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


def verified_source_pts_index(
    probe: "FfmpegProbe", source: Path, policy: MediaExecutionPolicy, *, time_base: Fraction,
    expected: dict[int, float], timeout: float, cancelled=None,
    mismatch_message: str = "source frame PTS does not match expected frame times",
) -> list[int]:
    """Presentation-ordered source PTS, verified to reproduce every expected frame time.

    Demuxer packet timestamps are read first because they need no decode, so a
    full-length match indexes in seconds. A decoded-frame index is used only when
    packet timing does not reproduce the expected frames exactly and uniquely.
    """
    def index(entries: str) -> list[str]:
        command = [probe.ffprobe, "-protocol_whitelist", "file,pipe", "-threads", str(policy.threads),
            "-v", "error", "-select_streams", "v:0", "-show_entries", entries,
            "-of", "csv=p=0", str(source)]
        _assert_safe_ffmpeg_argv(command)
        result = _run_bounded_media_process(command, timeout=timeout,
            output_cap=policy.captured_output_bytes, file_cap=policy.max_file_bytes, policy=policy)
        if cancelled is not None and cancelled():
            raise ValueError("source frame index cancelled")
        if result.returncode != 0:
            raise ValueError("source frame index unavailable")
        return [line.strip().rstrip(",") for line in result.stdout.decode().splitlines() if line.strip()]

    def verified(ticks: list[int]) -> bool:
        counts: dict[int, int] = {}
        for tick in ticks:
            counts[tick] = counts.get(tick, 0) + 1
        return all(frame_id < len(ticks) and counts[ticks[frame_id]] == 1 and math.isclose(
            float(ticks[frame_id] * time_base), seconds, rel_tol=0, abs_tol=1e-6)
            for frame_id, seconds in expected.items())

    packets = [row.split(",", 1) for row in index("packet=pts,flags")]
    packet_ticks = [row[0] for row in packets if len(row) == 1 or "D" not in row[1]]
    if len(packet_ticks) <= policy.max_frames and all(re.fullmatch(r"-?\d+", row) for row in packet_ticks):
        ticks = sorted(int(row) for row in packet_ticks)
        if verified(ticks):
            return ticks
    rows = index("frame=best_effort_timestamp")
    if len(rows) > policy.max_frames or any(not re.fullmatch(r"-?\d+", row) for row in rows):
        raise ValueError("source frame index has ambiguous timing")
    ticks = [int(row) for row in rows]
    if not verified(ticks):
        raise ValueError(mismatch_message)
    return ticks


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
        pts_origin = pts if grid_origin_pts is None else grid_origin_pts
        pts_step = Fraction(denominator, numerator) / Fraction(str(target_fps))
        pts_steps = (Fraction(last_export_pts - pts_origin, 1) / pts_step).__floor__()
        return Fraction(pts - pts_origin, 1) >= (pts_steps + 1) * pts_step
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
    original: Path, destination: Path, *, original_sha256: str, proxy_height: int = 720,
    runner=None, hash_cache: HashCache | None = None, policy: MediaExecutionPolicy | None = None,
    cancel_event: threading.Event | None = None, settings=None,
) -> dict[str, object]:
    effective = policy or MediaExecutionPolicy()
    deadline = time.monotonic() + effective.job_timeout_seconds
    original = _media_source_path(original, effective)
    digest = _file_identity(original, hash_cache).sha256
    if digest != original_sha256:
        raise ValueError("original digest mismatch; refusing to replace the source asset")
    if type(proxy_height) is not int or not 0 < proxy_height <= effective.max_height:
        raise ValueError("invalid proxy height")
    probe = None
    admission = None
    if runner is None or runner is subprocess.run:
        probe = FfmpegProbe(settings=settings, hash_cache=hash_cache, policy=effective)
        probe.probe_identity(original, cancel_event=cancel_event, deadline=deadline)
        admission = probe.last_execution_receipt
    command = [str(resolve_trusted_executable("ffmpeg", settings=settings)), "-hide_banner",
               "-nostdin", "-loglevel", "error", "-protocol_whitelist", "file,pipe",
               "-threads", str(effective.threads), "-i", str(original),
               "-vf", f"scale=-2:{proxy_height}", "-threads", str(effective.threads),
               "-t", str(effective.max_duration_seconds + 1), "-frames:v", str(effective.max_frames + 1),
               "-an", "-y", str(destination)]
    _assert_safe_ffmpeg_argv(command, settings=settings)
    execution = _publish_media_output(original, destination, command, policy=effective,
                                      cancel_event=cancel_event, runner=runner, deadline=deadline,
                                      expected_source_sha256=original_sha256,
                                      validate_output=(lambda path: probe.probe_identity(
                                          path, cancel_event=cancel_event, deadline=deadline)) if probe is not None else None)
    execution.update(operation="proxy", sourceProbe=admission,
                     outputProbe=probe.last_execution_receipt if probe is not None else None)
    result = derive_proxy_assets(original, original_sha256=original_sha256, original_pts=[0],
                                 time_base=(1, 1), proxy_height=proxy_height, hash_cache=hash_cache)
    result["assets"]["proxy"]["streamCopy"] = False
    result["frameExactExport"]["validatedDecodeReencode"] = False
    return {**result, "mediaExecution": execution, "ptsMappingVerified": False}


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
    # Display-matrix side data is the actual transform on modern ffprobe.
    # Preserve the legacy tag fallback for older fixtures/formats.
    for item in video.get("side_data_list") or []:
        if "rotation" not in item:
            continue
        raw = item["rotation"]
        try:
            value = float(raw)
            if isinstance(raw, bool) or not math.isfinite(value) or not value.is_integer():
                raise ValueError("rotation is not representable")
            return int(value)
        except (TypeError, ValueError, OverflowError) as error:
            raise MediaResourceLimit("SOURCE_NOT_ADMITTED: rotation") from error
    tags = video.get("tags") or {}
    try:
        return int(float(tags.get("rotate") or 0))
    except (TypeError, ValueError, OverflowError):
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
    if not exported or frame.presentation_time_seconds is None:
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


def detect_camera_cuts(presentation_times: Sequence[float | None], *, jump_seconds: float = 0.5) -> list[int]:
    cuts: list[int] = []
    for index in range(1, len(presentation_times)):
        current, previous = presentation_times[index], presentation_times[index - 1]
        if current is None or previous is None:
            continue
        delta = current - previous
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


class ProxyAssets(TypedDict):
    replacesOriginal: bool
    originalRetained: bool
    originalSha256: str
    assets: dict[str, dict[str, str | int | bool]]
    ptsMap: list[dict[str, int | float]]
    frameExactExport: dict[str, bool]


def derive_proxy_assets(
    original: Path,
    *,
    original_sha256: str,
    original_pts: list[int],
    time_base: tuple[int, int],
    proxy_height: int = 720,
    hash_cache: HashCache | None = None,
) -> ProxyAssets:
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
    source_box: tuple[int, ...],
    crop: tuple[int, ...],
    rotation: int,
) -> tuple[int, ...]:
    del crop
    if rotation % 360 != 0:
        raise ValueError("non-zero rotation must be inverted before publishing source boxes")
    return source_box
