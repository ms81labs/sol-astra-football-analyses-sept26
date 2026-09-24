"""C06 local media policy and child supervision (not a hosting sandbox)."""
from __future__ import annotations

import hashlib
import json
import math
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path


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


@dataclass(frozen=True)
class MediaExecutionPolicy:
    """Configured ceilings, not an estimate of CPU time from footage duration.

    No offline-match/live profile has been qualified. The default decoder is
    unchanged. A diagnostic caller may tighten or explicitly configure limits.
    """
    mode: str = "diagnostic_clip"
    max_duration_seconds: float = 120.0
    max_width: int = 1920
    max_height: int = 1080
    max_streams: int = 4
    max_source_bytes: int = 5 * 1024**3
    max_frames: int = 3600
    max_buffer_frames: int = 1
    max_buffer_bytes: int = 16 * 1024**2
    max_decoded_bytes: int | None = None
    diagnostic_tail_bytes: int = 65536
    captured_output_bytes: int = 4 * 1024**2
    job_timeout_seconds: float = 300.0
    stall_timeout_seconds: float = 30.0
    probe_timeout_seconds: float = 30.0
    export_timeout_seconds: float = 120.0
    cancellation_grace_seconds: float = 1.0
    cpu_soft_seconds: int = 300
    cpu_hard_seconds: int = 305
    address_space_bytes: int = 4 * 1024**3
    max_file_bytes: int = 8 * 1024**3
    threads: int = 2
    pixel_formats: tuple[str, ...] = (
        "yuv420p", "yuvj420p", "yuv422p", "yuvj422p", "yuv444p", "yuvj444p",
        "yuv420p10le", "yuv422p10le", "yuv444p10le", "nv12", "p010le",
        "bgr24", "rgb24", "gray", "gbrp", "rgba", "bgra",
    )

    def __post_init__(self) -> None:
        if self.mode not in {"diagnostic_clip", "offline_match", "live"}:
            raise ValueError("invalid media mode")
        for name, value in asdict(self).items():
            if name in {"mode", "pixel_formats"}:
                continue
            if name == "max_decoded_bytes" and value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a positive number")
            if not math.isfinite(value) or not 0 < value <= 2**63 - 1:
                raise ValueError(f"invalid {name}")
            if not name.endswith("_seconds") and not isinstance(value, int):
                raise ValueError(f"{name} must be an integer")
        if not isinstance(self.cpu_soft_seconds, int) or not isinstance(self.cpu_hard_seconds, int):
            raise ValueError("CPU limits must be integral seconds")
        if self.cpu_hard_seconds < self.cpu_soft_seconds:
            raise ValueError("CPU hard limit must be at least the soft limit")
        if not isinstance(self.pixel_formats, tuple) or not self.pixel_formats or any(
            not isinstance(item, str) or not item for item in self.pixel_formats
        ):
            raise ValueError("pixel formats must be an explicit tuple")

    @property
    def digest(self) -> str:
        raw = json.dumps({"version": "media-execution-v1", **asdict(self)},
                         sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(raw.encode()).hexdigest()

    def admit_mode(self) -> None:
        if self.mode != "diagnostic_clip":
            raise MediaResourceLimit(f"MODE_NOT_QUALIFIED: {self.mode}")

    def admit_source(self, identity) -> None:
        self.admit_mode()
        for name, maximum in (("width", self.max_width), ("height", self.max_height),
                              ("durationSeconds", self.max_duration_seconds),
                              ("frameCount", self.max_frames), ("byteSize", self.max_source_bytes)):
            value = getattr(identity, name, None)
            if value is not None and (isinstance(value, bool) or not math.isfinite(value) or value < 0 or value > maximum):
                raise MediaResourceLimit(f"SOURCE_NOT_ADMITTED: {name}")
        pixel_format = getattr(identity, "pixelFormat", None)
        if pixel_format is not None and pixel_format not in self.pixel_formats:
            raise MediaResourceLimit("SOURCE_NOT_ADMITTED: pixelFormat")

    def decode_budget(self, identity) -> tuple[int, int]:
        self.admit_source(identity)
        width, height = identity.width, identity.height
        if any(isinstance(n, bool) or not isinstance(n, int) or n <= 0 for n in (width, height)):
            raise MediaResourceLimit("SOURCE_NOT_ADMITTED: positive dimensions required")
        frame_size = width * height * 3  # Python integers cannot wrap on multiplication.
        if 2 * frame_size > self.max_buffer_bytes:
            raise MediaResourceLimit("ffmpeg decode exceeded resident-buffer cap")
        total = frame_size * self.max_frames
        if self.max_decoded_bytes is not None:
            total = min(total, self.max_decoded_bytes)
        if frame_size > total:
            raise MediaResourceLimit("ffmpeg decode exceeded output-byte cap")
        return frame_size, total

    def kernel_limits(self) -> dict[str, list[int]]:
        return {"RLIMIT_CPU": [self.cpu_soft_seconds, self.cpu_hard_seconds],
                "RLIMIT_AS": [self.address_space_bytes] * 2,
                "RLIMIT_FSIZE": [self.max_file_bytes] * 2}


class MediaExecution:
    """One child/process group, bounded lifetime, and post-exec limit evidence.

    Commands are controller-authored; public media callers must resolve and
    validate ffmpeg/ffprobe first. There is no request-facing arbitrary runner.
    A private pipe is closed before exec, so the media binary cannot forge the
    launcher's getrlimit receipt. Kernel limits do not imply FS/network isolation.
    """
    def __init__(self, command, *, policy, cwd, timeout, cancel_event=None, popen=None):
        policy.admit_mode()
        if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
            raise MediaResourceLimit("ffmpeg process exceeded wall-clock timeout")
        if cancel_event is not None and cancel_event.is_set():
            raise DecodeCancelled("ffmpeg process cancelled")
        if not sys.platform.startswith("linux"):
            raise MediaResourceLimit("PLATFORM_NOT_QUALIFIED: media kernel-limit launcher")
        self.policy = policy
        self.cancel_event = cancel_event
        self.started = time.monotonic()
        self.deadline = self.started + min(timeout, policy.job_timeout_seconds)
        self.demand_since: float | None = None
        self.reason: str | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._limits_data = bytearray()
        self.receipt = {
            "policyVersion": "media-execution-v1", "policySha256": policy.digest,
            "requestedPolicy": asdict(policy), "requestedLimits": policy.kernel_limits(),
            "enforcedLimits": {}, "outcome": "running", "reaped": False,
            "platform": sys.platform, "filesystemIsolation": False, "networkIsolation": False,
            "protocols": ["file", "pipe"], "fallback": "refuse",
            "effectiveWallTimeoutSeconds": min(timeout, policy.job_timeout_seconds),
        }
        binary = Path(command[0]).resolve(strict=True)
        executable_digest = hashlib.sha256()
        with binary.open("rb") as handle:
            while block := handle.read(1024 * 1024):
                executable_digest.update(block)
        self.receipt["executable"] = str(binary)
        self.receipt["executableSha256"] = executable_digest.hexdigest()
        self.receipt["commandSha256"] = hashlib.sha256(json.dumps(list(map(str, command))).encode()).hexdigest()
        self._limits_fd: int | None
        self._limits_fd, writer = os.pipe()
        os.set_blocking(self._limits_fd, False)
        launcher = Path(__file__).with_name("_media_launcher.py")
        argv = [sys.executable, "-I", "-S", str(launcher), str(writer),
                json.dumps(policy.kernel_limits(), separators=(",", ":")),
                executable_digest.hexdigest(), str(binary), *map(str, command[1:])]
        environment = dict(os.environ)
        for name in ("FFREPORT", "LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH"):
            environment.pop(name, None)
        environment.update(HOME=str(cwd), TMPDIR=str(cwd), OPENBLAS_NUM_THREADS="1")
        try:
            self.process = (popen or subprocess.Popen)(
                argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, start_new_session=True, pass_fds=(writer,), env=environment,
            )
        except BaseException:
            os.close(self._limits_fd)
            raise
        finally:
            os.close(writer)
        self.receipt["pid"] = getattr(self.process, "pid", None)
        self._watcher = threading.Thread(target=self._watch, name="ga-media-watch", daemon=True)
        self._watcher.start()

    def demand(self, active: bool) -> None:
        self.demand_since = time.monotonic() if active else None

    def progress(self) -> None:
        if self.demand_since is not None:
            self.demand_since = time.monotonic()

    def _watch(self) -> None:
        while not self._stop.wait(0.02):
            if self.cancel_event is not None and self.cancel_event.is_set():
                self.abort("CANCELLED")
                return
            now = time.monotonic()
            if now >= self.deadline:
                self.abort("JOB_DEADLINE")
                return
            demand = self.demand_since
            if demand is not None and now - demand >= self.policy.stall_timeout_seconds:
                self.abort("DECODER_STALL")
                return

    def _signal_group(self, number: int) -> None:
        pid = getattr(self.process, "pid", None)
        try:
            if isinstance(pid, int):
                os.killpg(pid, number)
            elif self.process.poll() is None:
                self.process.kill()  # A non-OS adapter cannot prove kernel enforcement.
        except ProcessLookupError:
            pass

    def _terminate(self) -> None:
        self._signal_group(signal.SIGTERM)
        try:
            self.process.wait(timeout=self.policy.cancellation_grace_seconds)
        except subprocess.TimeoutExpired:
            self._signal_group(signal.SIGKILL)
            self.process.wait(timeout=self.policy.cancellation_grace_seconds + 1)
        # A leader may have exited while a descendant still owns its pipes.
        self._signal_group(signal.SIGKILL)
        self.receipt["reaped"] = self.process.poll() is not None

    def abort(self, reason: str) -> None:
        with self._lock:
            if self.reason is None:
                self.reason = reason
            self.receipt["outcome"] = self.reason
            self._terminate()
            self.receipt["returnCode"] = self.process.poll()

    def _collect_limits(self) -> None:
        if self._limits_fd is None:
            return
        while True:
            try:
                chunk = os.read(self._limits_fd, 4096)
            except BlockingIOError:
                break
            if not chunk:
                break
            self._limits_data.extend(chunk)
            if len(self._limits_data) > 4096:
                self.reason = self.reason or "LIMIT_RECEIPT_INVALID"
                break
        if self._limits_data:
            try:
                actual = json.loads(self._limits_data)
                if actual != self.policy.kernel_limits():
                    raise ValueError("limit mismatch")
                self.receipt["enforcedLimits"] = actual
            except (ValueError, TypeError):
                self.reason = self.reason or "LIMIT_RECEIPT_INVALID"

    def check(self, *, tail: list[str] | None = None) -> None:
        self._collect_limits()
        code = self.process.poll()
        if code == 0 and isinstance(getattr(self.process, "pid", None), int) and not self.receipt["enforcedLimits"]:
            self.reason = self.reason or "LIMIT_INSTALLATION_UNVERIFIED"
        reason = self.reason
        error: RuntimeError
        if reason == "CANCELLED":
            error = DecodeCancelled("ffmpeg process cancelled")
        elif reason:
            messages = {"JOB_DEADLINE": "ffmpeg process exceeded wall-clock timeout",
                        "DECODER_STALL": "ffmpeg active decoder stalled",
                        "CAPTURE_LIMIT": "ffmpeg process exceeded captured-output cap",
                        "WORK_LIMIT": "ffmpeg decode exceeded output-byte cap"}
            error = MediaResourceLimit(messages.get(reason, reason))
        elif code not in (None, 0):
            error = DecoderFailed(code, tail=tail or [])
            reason = "CPU_LIMIT_SIGNAL" if code == -signal.SIGXCPU else (
                "FILE_LIMIT_SIGNAL" if code == -signal.SIGXFSZ else (
                    "CHILD_SIGNAL_UNKNOWN" if code < 0 else "CHILD_EXIT_FAILURE"))
        else:
            return
        self.receipt.update(outcome=reason, returnCode=code)
        vars(error)["execution_receipt"] = self.receipt
        raise error

    def close(self) -> None:
        if self._limits_fd is None:
            return
        self._stop.set()
        with self._lock:
            self._terminate()
        if threading.current_thread() is not self._watcher:
            self._watcher.join(timeout=self.policy.cancellation_grace_seconds + 2)
        self._collect_limits()
        os.close(self._limits_fd)
        self._limits_fd = None
        self.receipt.update(returnCode=self.process.poll(), elapsedSeconds=time.monotonic() - self.started)
        if self.receipt["outcome"] == "running":
            self.receipt["outcome"] = self.reason or ("completed" if self.process.poll() == 0 else "closed")


def media_failure_receipt(error: BaseException, *, policy=None, previous=None) -> dict:
    """Separate process execution from admission/publication failure, without unsafe error text."""
    receipt = dict(getattr(error, "execution_receipt", None) or previous or {})
    prior = receipt.get("outcome")
    if isinstance(error, DecodeCancelled):
        reason = "CANCELLED"
    elif isinstance(error, TruncatedStream):
        reason = "TRUNCATED_STREAM"
    elif prior and prior not in {"running", "completed", "external_runner_unverified", "not_started"}:
        reason = prior
    else:
        prefix = str(error).partition(":")[0]
        admitted_codes = {"MODE_NOT_QUALIFIED", "SOURCE_NOT_ADMITTED", "PLATFORM_NOT_QUALIFIED"}
        reason = prefix if prefix in admitted_codes else (
            "JOB_DEADLINE" if "wall-clock timeout" in str(error) else (
                "SOURCE_CHANGED" if "source changed" in str(error).lower() else "MEDIA_OPERATION_FAILED"))
    receipt.update(outcome=reason, published=False)
    if prior == "completed":
        receipt["childOutcome"] = "completed"
    if policy is not None:
        receipt.setdefault("policyVersion", "media-execution-v1")
        receipt.setdefault("policySha256", policy.digest)
    receipt.setdefault("enforcedLimits", {})
    receipt.setdefault("reaped", False)
    vars(error)["execution_receipt"] = receipt
    return receipt
