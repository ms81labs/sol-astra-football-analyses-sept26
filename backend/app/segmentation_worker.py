"""CPU preflight for a future sealed SAM shadow job; no SAM runtime here."""

from __future__ import annotations

import json
import math
import re
import stat
from collections.abc import Callable
from collections import Counter
from fractions import Fraction
from pathlib import Path
from time import monotonic

from .report_contracts import digest
from .segmentation import SegmentationRequest, request_identity
from .workbench.hashing import stream_sha256


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
