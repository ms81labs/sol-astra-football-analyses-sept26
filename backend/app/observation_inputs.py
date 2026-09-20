"""Pinned post-perception input reads for the existing review materializer.

The immutable generation supplies expected digests; the materializer consumes the
same bytes that were checked. This is same-match reuse, not cross-run inference
cache admission. Historical files are never rewritten to manufacture provenance.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path

from .semantic_commands import SemanticCommandError


def refused(code):
    raise SemanticCommandError(code, "Stored observations cannot be reused; recover or explicitly reprocess the source", status_code=409)


def _signature(stat):
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def _read(path: Path, *, parse=False):
    from .storage import _open_regular_file
    try:
        fd = _open_regular_file(path)
        with os.fdopen(fd, "rb") as handle:
            before = os.fstat(handle.fileno())
            digest = hashlib.sha256()
            chunks = [] if parse else None
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                if chunks is not None:
                    chunks.append(chunk)
            if _signature(before) != _signature(os.fstat(handle.fileno())) or _signature(before) != _signature(path.lstat()):
                refused("OBSERVATIONS_CHANGED_DURING_READ")
        payload = json.loads(b"".join(chunks), parse_constant=lambda _: refused("INVALID_OBSERVATIONS")) if parse else None
        return payload, {"sha256": digest.hexdigest(), "byteSize": before.st_size}, _signature(before)
    except FileNotFoundError:
        refused("CACHE_MISS")
    except (OSError, ValueError, UnicodeError):
        refused("INVALID_OBSERVATIONS")


@contextmanager
def observation_snapshot(storage, match_id, *, new_observations=False):
    match = storage.get_match(match_id)
    source_path = storage.get_match_input_path(match_id)
    source_payload, source, source_stat = _read(source_path, parse=match.inputMode != "video")
    try:
        ref = storage.current_generation(match_id)
        manifest, _ = storage.generations.manifest(match_id, ref.generationId)
    except FileNotFoundError:
        manifest = None
    if manifest is not None and manifest.sourceIdentity:
        if any(manifest.sourceIdentity.get(key) != value for key, value in source.items()):
            refused("SOURCE_IDENTITY_MISMATCH")
    root = storage._match_dir(match_id)
    path = source_path
    payload, binding, signature = source_payload, source, source_stat
    schema = "guerilla_tracking_import"
    if match.inputMode == "video":
        path = root / "raw_rows.json"
        payload, binding, signature = _read(path, parse=True)
        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            refused("INVALID_OBSERVATIONS")
        schema = "guerilla_combined_source_rows_v1"
    elif not payload and (root / "review_base_frames.json").is_file():
        path = root / "review_base_frames.json"
        payload, binding, signature = _read(path, parse=True)
    # A current generation is the authority for reuse, not a mutable sidecar.
    if manifest is not None and not new_observations:
        expected = manifest.observationDigest
        if expected is not None and expected != binding["sha256"]:
            refused("OBSERVATION_DIGEST_MISMATCH")
        previous = manifest.observationInputs
        if previous and (previous.get("matchId") != match_id or previous.get("source") != source
                         or previous.get("observations") != {**binding, "schema": schema}):
            refused("OBSERVATION_SCOPE_MISMATCH")
        if expected is None and path != source_path:
            refused("OBSERVATION_PROVENANCE_UNVERIFIED")
    record = {"schemaVersion": 1, "matchId": match_id,
        "reuseScope": "same_match_post_perception", "inputMode": match.inputMode,
        "source": source, "observations": {**binding, "schema": schema}}
    yield payload, record
    # Reject concurrent swaps/in-place changes before generation publication.
    try:
        if _signature(source_path.lstat()) != source_stat or _signature(path.lstat()) != signature:
            refused("OBSERVATIONS_CHANGED_DURING_MATERIALIZATION")
    except OSError:
        refused("OBSERVATIONS_CHANGED_DURING_MATERIALIZATION")
