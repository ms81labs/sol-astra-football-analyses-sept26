"""CPU preflight for a future sealed SAM shadow job; no SAM runtime here."""

from __future__ import annotations

import json
import hashlib
import math
import os
import re
import shutil
import stat
import tempfile
from collections.abc import Callable, Mapping
from collections import Counter
from fractions import Fraction
from io import BytesIO
from pathlib import Path
from time import monotonic

from .report_contracts import digest
from .segmentation import SegmentationRequest, request_identity
from .workbench.hashing import stream_sha256


def sam3_prompt_requests(request: SegmentationRequest) -> tuple[dict[str, int], list[dict]]:
    """Map source-frame prompts to the official Object Multiplex request shape."""
    frame_indices = {frame.frameId: index for index, frame in enumerate(request.frames)}
    object_ids = {name: index + 1 for index, name in enumerate(sorted({
        prompt.objectId for prompt in request.prompts}))}
    by_object_frame: dict[tuple[str, int], dict] = {}
    for prompt in request.prompts:
        if prompt.box is not None:
            # Box prompts take SAM3's semantic path, which resets state and ignores obj_id.
            raise ValueError("SAM3.1 box prompts require verified object association")
        x, y = prompt.point
        if not (0 <= x < request.width and 0 <= y < request.height):
            raise ValueError("shadow prompt exceeds source frame geometry")
        key = (prompt.objectId, prompt.frameId)
        if key not in by_object_frame:
            by_object_frame[key] = {"type": "add_prompt", "frame_index": frame_indices[prompt.frameId],
                "obj_id": object_ids[prompt.objectId], "points": [],
                "point_labels": [], "rel_coordinates": True}
        by_object_frame[key]["points"].append([x / request.width, y / request.height])
        by_object_frame[key]["point_labels"].append(1)
    return object_ids, list(by_object_frame.values())


def stage_sam_source_window(source: Path, request: SegmentationRequest, workspace: Path, *,
                            timeout_seconds: float = 300) -> tuple[Path, dict]:
    """Stage only exact requested source frames as SAM's numbered image folder."""
    from PIL import Image
    from .remote_contracts import canonical_json_bytes
    from .workbench.media import (FfmpegProbe, _ShowinfoParser,
        _assert_safe_ffmpeg_argv, _run_bounded_media_process)
    from .workbench.media_execution import MediaExecutionPolicy

    if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) \
            or not 0 < timeout_seconds <= 3600:
        raise ValueError("invalid shadow window deadline")
    request_digest = request_identity(request)
    if request_digest is None or request.modelAlias != "sam31-video" \
            or request.executionMode != "sam31_object_multiplex" or request.precision != "bf16":
        raise ValueError("shadow runtime identity is invalid")
    sam3_prompt_requests(request)
    source, workspace = Path(source), Path(workspace)
    if workspace.is_symlink() or not workspace.is_dir():
        raise ValueError("shadow window workspace is unavailable")
    source_stat = source.stat(follow_symlinks=False)
    if not stat.S_ISREG(source_stat.st_mode) \
            or stream_sha256(source).sha256 != request.sourceSha256:
        raise ValueError("shadow source identity mismatch")
    started = monotonic()
    policy = MediaExecutionPolicy(max_duration_seconds=10_800, max_width=4096,
        max_height=4096, max_frames=500_000, job_timeout_seconds=timeout_seconds,
        probe_timeout_seconds=min(30, timeout_seconds), captured_output_bytes=8 * 1024**2)
    probe = FfmpegProbe(policy=policy)
    identity = probe.probe_identity(source)
    if identity.sourceSha256 != request.sourceSha256 or (identity.width, identity.height) != \
            (request.width, request.height) or not identity.timeBaseNum or not identity.timeBaseDen:
        raise ValueError("shadow source identity mismatch")
    command = [probe.ffprobe, "-protocol_whitelist", "file,pipe", "-threads", str(policy.threads),
        "-v", "error", "-select_streams", "v:0", "-show_entries",
        "frame=best_effort_timestamp", "-of", "csv=p=0", str(source)]
    _assert_safe_ffmpeg_argv(command)
    index = _run_bounded_media_process(command, timeout=min(30, timeout_seconds),
        output_cap=policy.captured_output_bytes, file_cap=policy.max_file_bytes, policy=policy)
    if index.returncode != 0:
        raise ValueError("shadow source frame index unavailable")
    rows = [line.strip().rstrip(",") for line in index.stdout.decode().splitlines() if line.strip()]
    if len(rows) > policy.max_frames or any(not re.fullmatch(r"-?\d+", row) for row in rows):
        raise ValueError("shadow source frame index ambiguous")
    ticks = [int(row) for row in rows]
    counts = Counter(ticks)
    time_base = Fraction(identity.timeBaseNum, identity.timeBaseDen)
    if any(frame.frameId >= len(ticks) or counts[ticks[frame.frameId]] != 1 or not math.isclose(
        float(ticks[frame.frameId] * time_base), frame.ptsSeconds, rel_tol=0, abs_tol=1e-6)
        for frame in request.frames):
        raise ValueError("shadow source frame PTS mismatch")
    root = Path(tempfile.mkdtemp(prefix="sam-window-", dir=workspace))
    os.chmod(root, 0o700)
    try:
        frames = []
        total_bytes = 0
        for local_index, frame in enumerate(request.frames):
            remaining = timeout_seconds - (monotonic() - started)
            if remaining <= 0:
                raise ValueError("shadow window deadline expired")
            command = [probe.ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "info",
                "-protocol_whitelist", "file,pipe", "-threads", str(policy.threads),
                "-noautorotate", "-ss", str(frame.ptsSeconds), "-copyts", "-i", str(source),
                "-map", "0:v:0", "-an", "-vf", "showinfo", "-frames:v", "1",
                "-fps_mode", "passthrough", "-f", "image2pipe", "-vcodec", "png", "pipe:1"]
            _assert_safe_ffmpeg_argv(command)
            result = _run_bounded_media_process(command, timeout=min(30, remaining),
                output_cap=64 * 1024**2, file_cap=policy.max_file_bytes, policy=policy)
            parser = _ShowinfoParser()
            times = parser.feed(result.stderr) + parser.finish()
            if result.returncode != 0 or not times or times[0][1] != ticks[frame.frameId]:
                raise ValueError("shadow decoded frame PTS mismatch")
            with Image.open(BytesIO(result.stdout)) as image:
                if image.format != "PNG" or image.size != (request.width, request.height):
                    raise ValueError("shadow decoded frame geometry mismatch")
                image.verify()
            total_bytes += len(result.stdout)
            if total_bytes > 512 * 1024**2:
                raise ValueError("shadow window exceeds byte limit")
            filename = f"{local_index}.png"
            descriptor = os.open(root / filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                getattr(os, "O_NOFOLLOW", 0), 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(result.stdout)
            frames.append({"localIndex": local_index, "sourceFrameId": frame.frameId,
                "ptsSeconds": frame.ptsSeconds, "path": filename,
                "sha256": hashlib.sha256(result.stdout).hexdigest(), "sizeBytes": len(result.stdout)})
        final_stat = source.stat(follow_symlinks=False)
        if not stat.S_ISREG(final_stat.st_mode) or (
            final_stat.st_dev, final_stat.st_ino, final_stat.st_size) != (
            source_stat.st_dev, source_stat.st_ino, source_stat.st_size
        ) or stream_sha256(source).sha256 != request.sourceSha256:
            raise ValueError("shadow source changed during staging")
        if monotonic() - started >= timeout_seconds:
            raise ValueError("shadow window deadline expired")
        manifest = {"schemaVersion": 1, "sourceSha256": request.sourceSha256,
            "requestDigest": request_digest, "frames": frames}
        (root / "window.json").write_bytes(canonical_json_bytes(manifest))
        return root, manifest
    except Exception:
        try:
            shutil.rmtree(root)
        except Exception:
            raise RuntimeError("shadow window cleanup could not be confirmed") from None
        raise


def load_sealed_shadow_bundle(root: Path):
    """Recheck transferred inputs in the worker before loading a model."""
    from .daytona import _open_preflight_regular_file, _preflight_file_identity
    from .remote_contracts import (JobReceipt, JobRequest, confined_path,
        load_canonical_json, validate_receipt_files, validate_shadow_inputs)

    try:
        with os.fdopen(_open_preflight_regular_file(confined_path(root, "job-request.json")), "rb") as handle:
            request = JobRequest.from_mapping(load_canonical_json(handle))
        with os.fdopen(_open_preflight_regular_file(confined_path(root, request.receipt_path)), "rb") as handle:
            receipt = JobReceipt.from_mapping(load_canonical_json(handle))
        for entry in receipt.files:
            if _preflight_file_identity(confined_path(root, entry.relative_path)) != (entry.sha256, entry.size_bytes):
                raise ValueError
        validate_receipt_files(root, request, receipt)
        shadow = validate_shadow_inputs(request, receipt)
        segmentation = validate_sealed_shadow_request(
            confined_path(root, "inputs/segmentation-request.json"), shadow)
        return request, receipt, segmentation
    except Exception:
        raise ValueError("sealed shadow bundle is invalid") from None


def validate_sealed_shadow_request(path: Path, shadow: Mapping[str, object]) -> SegmentationRequest:
    """Parse the fixed sealed request before a shadow sandbox can be allocated."""
    from .daytona import _open_preflight_regular_file
    from .remote_contracts import MAX_RESULT_BYTES

    try:
        descriptor = _open_preflight_regular_file(path)
        with os.fdopen(descriptor, "rb") as handle:
            raw = handle.read(MAX_RESULT_BYTES + 1)
        request = SegmentationRequest.model_validate_json(raw)
        canonical = json.dumps(request.model_dump(mode="json"), sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode()
        if (raw != canonical or len(raw) > MAX_RESULT_BYTES
                or hashlib.sha256(raw).hexdigest() != shadow["requestDigest"]
                or request_identity(request) != shadow["requestDigest"]
                or request.sourceSha256 != shadow["sourceSha256"]
                or request.checkpointDigest != shadow["checkpointDigest"]
                or request.modelAlias != "sam31-video"
                or request.executionMode != "sam31_object_multiplex"
                or request.precision != "bf16"):
            raise ValueError
        sam3_prompt_requests(request)
        return request
    except Exception:
        raise ValueError("sealed shadow request is invalid") from None


def preflight_shadow_window(storage, match_id: str, generation_id: str, payload: dict, *,
                            checkpoint_path: Path, approved_model_digest: str,
                            approved_worker_digest: str, approved_crop_digest: str,
                            deadline_seconds: float, cancelled: bool | Callable[[], bool] = False) -> dict:
    if type(cancelled) is not bool and not callable(cancelled):
        raise ValueError("invalid shadow cancellation signal")
    def cancellation_requested() -> bool:
        return cancelled() if callable(cancelled) else cancelled
    if cancellation_requested():
        raise ValueError("shadow job cancelled before admission")
    if type(deadline_seconds) not in (int, float) or not math.isfinite(deadline_seconds) \
            or not 0 < deadline_seconds <= 3600:
        raise ValueError("invalid shadow job deadline")
    started = monotonic()
    if storage.current_generation(match_id).generationId != generation_id:
        raise ValueError("stale shadow generation")
    match = storage.get_match(match_id)
    if match.inputMode != "video" or not match.config.rights.cloudPermission \
            or match.config.rights.processingScope == "local_only":
        raise ValueError("source rights do not permit remote shadow processing")
    request = SegmentationRequest.model_validate_json(json.dumps(payload))
    identity = request_identity(request)
    if identity is None or request.modelAlias != "sam31-video" \
            or request.executionMode != "sam31_object_multiplex" or request.precision != "bf16" \
            or request.modelDigest != approved_model_digest \
            or request.workerDigest != approved_worker_digest \
            or request.cropDigest != approved_crop_digest:
        raise ValueError("shadow runtime identity is not approved")
    sam3_prompt_requests(request)
    source = storage.get_match_input_path(match_id)
    checkpoint = Path(checkpoint_path)
    for path in (source, checkpoint):
        if path.is_symlink() or not stat.S_ISREG(path.stat(follow_symlinks=False).st_mode):
            raise ValueError("shadow input must be a regular owned file")
    source_sha = stream_sha256(source).sha256
    checkpoint_sha = stream_sha256(checkpoint).sha256
    if request.sourceSha256 != source_sha or source_sha != storage.source_sha256(match_id) \
            or request.checkpointDigest != checkpoint_sha:
        raise ValueError("shadow source or checkpoint digest mismatch")
    with storage.generation_snapshot(match_id, generation_id=generation_id):
        frames = storage.load_frames(match_id, generation_id=generation_id)
    frame_pts = {frame.frameId: frame.timestamp for frame in frames}
    if len(frame_pts) != len(frames) or any(frame_pts.get(item.frameId) != item.ptsSeconds
            for item in request.frames) \
            or request.baseTrackingDigest != digest([frame.model_dump(mode="json") for frame in frames]):
        raise ValueError("shadow frames do not match frozen tracking")
    from .workbench.media import FfmpegProbe, _assert_safe_ffmpeg_argv, _run_bounded_media_process
    from .workbench.media_execution import MediaExecutionPolicy

    timeout = min(30.0, deadline_seconds)
    policy = MediaExecutionPolicy(max_duration_seconds=10_800,
        max_frames=500_000, job_timeout_seconds=timeout, probe_timeout_seconds=timeout,
        cpu_soft_seconds=31, cpu_hard_seconds=32, captured_output_bytes=8 * 1024**2)
    probe = FfmpegProbe(policy=policy)
    media_identity = probe.probe_identity(source)
    if cancellation_requested():
        raise ValueError("shadow job cancelled during preflight")
    # ponytail: only full-frame source geometry is admitted until a sealed crop manifest binds cropped pixels.
    if (media_identity.sourceSha256 != source_sha or (request.width, request.height) != (media_identity.width, media_identity.height)
            or not media_identity.timeBaseNum or not media_identity.timeBaseDen):
        raise ValueError("shadow source dimensions or identity mismatch")
    command = [probe.ffprobe, "-protocol_whitelist", "file,pipe", "-threads", str(policy.threads),
        "-v", "error", "-select_streams", "v:0", "-show_entries", "frame=best_effort_timestamp",
        "-of", "csv=p=0", str(source)]
    _assert_safe_ffmpeg_argv(command)
    result = _run_bounded_media_process(command, timeout=timeout,
        output_cap=policy.captured_output_bytes, file_cap=policy.max_file_bytes, policy=policy)
    if cancellation_requested():
        raise ValueError("shadow job cancelled during preflight")
    if result.returncode != 0:
        raise ValueError("shadow source frame index unavailable")
    rows = [line.strip().rstrip(",") for line in result.stdout.decode().splitlines() if line.strip()]
    if len(rows) > policy.max_frames or any(not re.fullmatch(r"-?\d+", row) for row in rows):
        raise ValueError("shadow source frame index ambiguous")
    ticks = [int(row) for row in rows]
    tick_counts = Counter(ticks)
    time_base = Fraction(media_identity.timeBaseNum, media_identity.timeBaseDen)
    if any(item.frameId >= len(ticks) or tick_counts[ticks[item.frameId]] != 1
           or not math.isclose(float(ticks[item.frameId] * time_base), item.ptsSeconds,
                               rel_tol=0, abs_tol=1e-6) for item in request.frames):
        raise ValueError("shadow source frame PTS mismatch")
    for path, expected, label in ((source, source_sha, "source"),
                                  (checkpoint, checkpoint_sha, "checkpoint")):
        if path.is_symlink() or not stat.S_ISREG(path.stat(follow_symlinks=False).st_mode) \
                or stream_sha256(path).sha256 != expected:
            raise ValueError(f"shadow {label} changed during preflight")
    if storage.current_generation(match_id).generationId != generation_id:
        raise ValueError("stale shadow generation")
    live_match = storage.get_match(match_id)
    if live_match.inputMode != "video" or not live_match.config.rights.cloudPermission \
            or live_match.config.rights.processingScope == "local_only":
        raise ValueError("source rights changed during shadow preflight")
    if cancellation_requested():
        raise ValueError("shadow job cancelled during preflight")
    if monotonic() - started >= deadline_seconds:
        raise ValueError("shadow job deadline expired during preflight")
    return {"schemaVersion": 1, "matchId": match_id, "generationId": generation_id,
        "requestDigest": identity, "sourceSha256": source_sha,
        "checkpointDigest": checkpoint_sha, "deadlineSeconds": deadline_seconds,
        "jobIdentity": digest({"matchId": match_id, "generationId": generation_id,
            "requestDigest": identity, "checkpointDigest": checkpoint_sha})}
