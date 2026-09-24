"""CPU preflight for a future sealed SAM shadow job; no SAM runtime here."""

from __future__ import annotations

import json
import math
import stat
from pathlib import Path

from .report_contracts import digest
from .segmentation import SegmentationRequest, request_identity
from .workbench.hashing import stream_sha256


def preflight_shadow_window(storage, match_id: str, generation_id: str, payload: dict, *,
                            checkpoint_path: Path, approved_model_digest: str,
                            approved_worker_digest: str, approved_crop_digest: str,
                            deadline_seconds: float, cancelled: bool = False) -> dict:
    if cancelled:
        raise ValueError("shadow job cancelled before admission")
    if type(deadline_seconds) not in (int, float) or not math.isfinite(deadline_seconds) \
            or not 0 < deadline_seconds <= 3600:
        raise ValueError("invalid shadow job deadline")
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
    return {"schemaVersion": 1, "matchId": match_id, "generationId": generation_id,
        "requestDigest": identity, "sourceSha256": source_sha,
        "checkpointDigest": checkpoint_sha, "deadlineSeconds": deadline_seconds,
        "jobIdentity": digest({"matchId": match_id, "generationId": generation_id,
            "requestDigest": identity, "checkpointDigest": checkpoint_sha})}
