"""GA-02 source-clock identity, GA-15 sampling audit, GA-16 FrameSource adapters."""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Literal

from .contracts import FrameIdentity, SamplingReceipt, SourceClockIdentity


ColourOrder = Literal["bgr", "rgb"]


@dataclass(frozen=True)
class DecodedFrame:
    source_frame_index: int
    pts: int | None
    presentation_time_seconds: float
    width: int
    height: int
    colour_order: ColourOrder
    rotation: int
    payload: bytes
    backend: str
    crop: tuple[int, int, int, int] | None = None


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

    def __init__(self, frames: list[DecodedFrame], identity: SourceClockIdentity):
        self._frames = list(frames)
        self._identity = identity

    def probe(self, path: Path) -> SourceClockIdentity:
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else self._identity.sourceSha256
        return self._identity.model_copy(update={"sourceSha256": digest, "byteSize": path.stat().st_size if path.exists() else 0})

    def iter_frames(self, path: Path, *, cancel_event: threading.Event | None = None) -> Iterator[DecodedFrame]:
        for frame in self._frames:
            if cancel_event is not None and cancel_event.is_set():
                return
            yield frame


class OpenCvFrameSource(FrameSource):
    name = "opencv"

    def probe(self, path: Path) -> SourceClockIdentity:
        payload = path.read_bytes()
        identity = SourceClockIdentity(
            sourceSha256=hashlib.sha256(payload).hexdigest(),
            byteSize=len(payload),
        )
        try:
            import cv2  # type: ignore
        except Exception:
            return identity
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            return identity.model_copy(update={"decodeErrors": ["opencv_open_failed"]})
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0) or None
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0) or None
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0) or None
        frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        duration = (frame_count / fps) if fps and frame_count else None
        capture.release()
        return identity.model_copy(
            update={
                "width": width,
                "height": height,
                "nominalFps": fps,
                "durationSeconds": duration,
                "pixelFormat": "bgr24",
            }
        )

    def iter_frames(self, path: Path, *, cancel_event: threading.Event | None = None) -> Iterator[DecodedFrame]:
        import cv2  # type: ignore

        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            return
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0) or 1.0
        index = 0
        try:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    return
                ok, image = capture.read()
                if not ok:
                    return
                payload = image.tobytes() if hasattr(image, "tobytes") else bytes(image)
                height, width = (int(image.shape[0]), int(image.shape[1])) if hasattr(image, "shape") else (0, 0)
                yield DecodedFrame(
                    source_frame_index=index,
                    pts=index,
                    presentation_time_seconds=index / fps,
                    width=width,
                    height=height,
                    colour_order="bgr",
                    rotation=0,
                    payload=payload,
                    backend=self.name,
                )
                index += 1
        finally:
            capture.release()


class FfmpegProbe:
    """GA-16 FFmpeg/ffprobe jobs with safe arguments and cancellation."""

    def __init__(self, ffprobe: str = "ffprobe", ffmpeg: str = "ffmpeg"):
        self.ffprobe = ffprobe
        self.ffmpeg = ffmpeg

    def probe_identity(self, path: Path, *, runner=subprocess.run) -> SourceClockIdentity:
        command = [
            self.ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        _assert_safe_ffmpeg_argv(command)
        completed = runner(command, check=True, capture_output=True, text=True, timeout=30)
        payload = json.loads(completed.stdout)
        video = next((stream for stream in payload.get("streams", []) if stream.get("codec_type") == "video"), {})
        audio_tracks = sum(1 for stream in payload.get("streams", []) if stream.get("codec_type") == "audio")
        num, den = _parse_rate(video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1")
        time_base_num, time_base_den = _parse_rate(video.get("time_base") or "1/1")
        fps = (num / den) if den else None
        duration = float(payload.get("format", {}).get("duration") or 0.0) or None
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return SourceClockIdentity(
            sourceSha256=digest,
            byteSize=path.stat().st_size,
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
        command = [
            self.ffmpeg,
            "-hide_banner",
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
        _assert_safe_ffmpeg_argv(command)
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError("ffmpeg export cancelled")
        runner(command, check=True, capture_output=True, timeout=120)


def _assert_safe_ffmpeg_argv(command: list[str]) -> None:
    if not command or command[0] not in {"ffmpeg", "ffprobe"} and os.path.basename(command[0]) not in {"ffmpeg", "ffprobe"}:
        raise ValueError("refusing unexpected media binary")
    joined = shlex.join(command)
    if any(token in joined for token in ("`", "$(", ";", "|", "&&", "\n")):
        raise ValueError("refusing unsafe ffmpeg arguments")


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
    temporal_policy: str = "clip_local_index_modulo"
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
