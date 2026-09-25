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
from fractions import Fraction
from io import BytesIO
from pathlib import Path, PurePosixPath
from time import monotonic

from .report_contracts import digest
from .segmentation import FrameMask, SegmentationRequest, request_identity
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
        _assert_safe_ffmpeg_argv, _run_bounded_media_process, verified_source_pts_index)
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
    ticks = verified_source_pts_index(probe, source, policy,
        time_base=Fraction(identity.timeBaseNum, identity.timeBaseDen),
        expected={frame.frameId: frame.ptsSeconds for frame in request.frames},
        timeout=min(30, timeout_seconds), mismatch_message="shadow source frame PTS mismatch")
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
        validate_sam_source_window(root, request)
        return root, manifest
    except Exception:
        try:
            shutil.rmtree(root)
        except Exception:
            raise RuntimeError("shadow window cleanup could not be confirmed") from None
        raise


def validate_sam_source_window(root: Path, request: SegmentationRequest) -> dict:
    """Recheck a numbered source window before a worker loads any model."""
    from PIL import Image
    from .daytona import _open_preflight_regular_file
    from .remote_contracts import load_canonical_json

    try:
        root = Path(root)
        if not root.is_absolute() or root.is_symlink() or not root.is_dir():
            raise ValueError
        identity = request_identity(request)
        if identity is None:
            raise ValueError
        with os.fdopen(_open_preflight_regular_file(root / "window.json"), "rb") as handle:
            manifest = load_canonical_json(handle)
        if not isinstance(manifest, dict) or set(manifest) != {
            "schemaVersion", "sourceSha256", "requestDigest", "frames"
        } or type(manifest["schemaVersion"]) is not int or manifest["schemaVersion"] != 1 \
                or manifest["sourceSha256"] != request.sourceSha256 \
                or manifest["requestDigest"] != identity \
                or not isinstance(manifest["frames"], list) \
                or len(manifest["frames"]) != len(request.frames):
            raise ValueError
        expected_files = {"window.json"} | {f"{index}.png" for index in range(len(request.frames))}
        if {path.name for path in root.iterdir()} != expected_files:
            raise ValueError
        total = 0
        for index, (item, frame) in enumerate(zip(manifest["frames"], request.frames)):
            filename = f"{index}.png"
            if not isinstance(item, dict) or set(item) != {
                "localIndex", "sourceFrameId", "ptsSeconds", "path", "sha256", "sizeBytes"
            } or type(item["localIndex"]) is not int or item["localIndex"] != index \
                    or type(item["sourceFrameId"]) is not int or item["sourceFrameId"] != frame.frameId \
                    or type(item["ptsSeconds"]) not in (int, float) \
                    or item["ptsSeconds"] != frame.ptsSeconds or item["path"] != filename \
                    or type(item["sizeBytes"]) is not int or not 0 < item["sizeBytes"] <= 64 * 1024**2:
                raise ValueError
            with os.fdopen(_open_preflight_regular_file(root / filename), "rb") as handle:
                payload = handle.read(64 * 1024**2 + 1)
            total += len(payload)
            if len(payload) != item["sizeBytes"] or total > 512 * 1024**2 \
                    or hashlib.sha256(payload).hexdigest() != item["sha256"]:
                raise ValueError
            with Image.open(BytesIO(payload)) as image:
                if image.format != "PNG" or image.size != (request.width, request.height):
                    raise ValueError
                image.verify()
        return manifest
    except Exception:
        raise ValueError("sealed shadow window is invalid") from None


def run_sam3_multiplex_window(window_root: Path, checkpoint_path: Path,
                             request: SegmentationRequest, *, predictor_factory: Callable,
                             deadline_seconds: float = 300,
                             cancelled: bool | Callable[[], bool] = False) -> list[FrameMask]:
    """Run the official session protocol; only a qualified worker may supply its factory."""
    import numpy as np
    from .daytona import _preflight_file_identity

    if type(deadline_seconds) not in (int, float) or not math.isfinite(deadline_seconds) \
            or not 0 < deadline_seconds <= 3600 or not callable(predictor_factory) \
            or (type(cancelled) is not bool and not callable(cancelled)):
        raise ValueError("invalid SAM runner controls")
    started = monotonic()
    def check_live() -> None:
        cancellation_requested = cancelled() if callable(cancelled) else cancelled
        if cancellation_requested:
            raise ValueError("SAM job cancelled")
        if monotonic() - started >= deadline_seconds:
            raise ValueError("SAM job deadline expired")

    check_live()
    validate_sam_source_window(window_root, request)
    if request.modelAlias != "sam31-video" or request.executionMode != "sam31_object_multiplex" \
            or request.precision != "bf16":
        raise ValueError("SAM runtime identity is invalid")
    checkpoint_path = Path(checkpoint_path)
    if _preflight_file_identity(checkpoint_path)[0] != request.checkpointDigest:
        raise ValueError("SAM checkpoint identity mismatch")
    object_ids, prompts = sam3_prompt_requests(request)
    if request.width * request.height * len(request.frames) * len(object_ids) > 512 * 1024**2:
        raise ValueError("SAM mask window exceeds byte limit")
    check_live()
    predictor = predictor_factory(checkpoint_path, request.maxObjects)
    response = predictor.handle_request({"type": "start_session", "resource_path": str(window_root)})
    session_id = response.get("session_id") if isinstance(response, dict) else None
    if not isinstance(session_id, str) or not session_id:
        raise ValueError("SAM session identity is invalid")
    try:
        for prompt in prompts:
            check_live()
            predictor.handle_request({**prompt, "session_id": session_id})
        by_id = {value: key for key, value in object_ids.items()}
        seen_frames: set[int] = set()
        masks: list[FrameMask] = []
        total_runs = 0
        stream = predictor.handle_stream_request({"type": "propagate_in_video",
            "session_id": session_id, "max_frame_num_to_track": len(request.frames)})
        try:
            for item in stream:
                check_live()
                if not isinstance(item, dict) or type(item.get("frame_index")) is not int:
                    raise ValueError("SAM output frame identity is invalid")
                index = item["frame_index"]
                if index in seen_frames or not 0 <= index < len(request.frames):
                    raise ValueError("SAM output frame identity is invalid")
                seen_frames.add(index)
                outputs = item.get("outputs")
                if not isinstance(outputs, dict):
                    raise ValueError("SAM output masks are invalid")
                ids = np.asarray(outputs.get("out_obj_ids"))
                pixels = np.asarray(outputs.get("out_binary_masks"))
                if ids.ndim != 1 or pixels.shape != (len(ids), request.height, request.width) \
                        or pixels.dtype != np.bool_:
                    raise ValueError("SAM output masks are invalid")
                seen_objects: set[int] = set()
                for object_id, mask in zip(ids, pixels, strict=True):
                    if not isinstance(object_id, (int, np.integer)) or int(object_id) not in by_id \
                            or int(object_id) in seen_objects:
                        raise ValueError("SAM output object identity is invalid")
                    seen_objects.add(int(object_id))
                    # Column-major RLE starting with a background run, vectorised.
                    flat = mask.T.reshape(-1)
                    changes = np.flatnonzero(flat[1:] != flat[:-1]) + 1
                    total_runs += len(changes) + int(flat[0])
                    if total_runs > 4_000_000:
                        raise ValueError("SAM mask output exceeds byte limit")
                    runs = np.diff(np.concatenate(([0], changes, [flat.size]))).tolist()
                    counts = [0, *runs] if flat[0] else runs
                    frame = request.frames[index]
                    masks.append(FrameMask(objectId=by_id[int(object_id)], sourceFrameId=frame.frameId,
                        ptsSeconds=frame.ptsSeconds,
                        rle={"size": [request.height, request.width], "counts": counts}))
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                close()
        if len(seen_frames) != len(request.frames):
            raise ValueError("SAM output window is incomplete")
        validate_sam_source_window(window_root, request)
        if _preflight_file_identity(checkpoint_path)[0] != request.checkpointDigest:
            raise ValueError("SAM checkpoint changed during inference")
        check_live()
        return masks
    finally:
        predictor.handle_request({"type": "close_session", "session_id": session_id})


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
        expected_inputs = {PurePosixPath("inputs/checkpoint.bin"),
            PurePosixPath("inputs/segmentation-request.json")}
        if shadow["schemaVersion"] == 2:
            validate_sam_source_window(confined_path(root, "inputs/window"), segmentation)
            expected_inputs.update(PurePosixPath(f"inputs/window/{index}.png")
                for index in range(len(segmentation.frames)))
        if {entry.relative_path for entry in receipt.files if entry.role == "runtime_artifact"
            and entry.relative_path.parts[0] == "inputs"} != expected_inputs:
            raise ValueError
        if "samRelease" in request.config:
            _validate_sam_release(root, request, receipt, segmentation)
        return request, receipt, segmentation
    except Exception:
        raise ValueError("sealed shadow bundle is invalid") from None


def retain_shadow_mask_result(storage, bundle_root: Path, output) -> dict:
    """Retain a validated shadow result for review; CPU release proof never accepts quality."""
    from .daytona import DaytonaExecutionResult
    from .remote_contracts import MAX_SEGMENTATION_RESULT_BYTES, canonical_json_bytes, validate_completion
    from .remote_worker import _read_result_artifact
    from .segmentation import MaskResult, load_result, save_result
    from .workbench.artifacts import ArtifactStore

    job, receipt, request = load_sealed_shadow_bundle(bundle_root)
    try:
        if type(output) is not DaytonaExecutionResult or output.result.schema_version != 3 \
                or "samRelease" not in job.config:
            raise ValueError
        validate_completion(output.staging_root, job, receipt, output.result, output.completion)
        raw = _read_result_artifact(output, output.processor_path,
            job_id=job.job_id, match_id=job.match_id,
            maximum_bytes=MAX_SEGMENTATION_RESULT_BYTES, declared_path_key="maskResultPath")
        mask = MaskResult.model_validate_json(raw)
        actual = mask.model_dump(mode="json")
        expected = request.model_dump(mode="json")
        bound = ("sourceSha256", "baseTrackingDigest", "modelAlias", "modelDigest",
            "checkpointDigest", "workerDigest", "executionMode", "width", "height",
            "intervalStart", "intervalEnd", "frames", "prompts")
        objects = {prompt.objectId: prompt.trackId for prompt in request.prompts}
        if mask.requestDigest != request_identity(request) \
                or any(actual[key] != expected[key] for key in bound) \
                or {item.objectId: item.trackId for item in mask.objects} != objects:
            raise ValueError
    except Exception:
        raise ValueError("shadow mask result is invalid") from None

    shadow = job.config["shadowSegmentation"]
    match_id = job.match_id
    with storage._generation_lock(match_id):
        if storage.current_generation(match_id).generationId != shadow["generationId"]:
            raise ValueError("shadow generation changed before mask retention")
        match = storage.get_match(match_id)
        if match.inputMode != "video" or not match.config.rights.cloudPermission \
                or match.config.rights.processingScope == "local_only":
            raise ValueError("shadow rights changed before mask retention")
        if storage.source_sha256(match_id) != shadow["sourceSha256"]:
            raise ValueError("shadow source changed before mask retention")
        store = ArtifactStore(storage.storage_root / "artifacts")
        mask_digest = save_result(store, mask)
        if load_result(store, mask_digest) != mask \
                or storage.source_sha256(match_id) != shadow["sourceSha256"]:
            raise ValueError("shadow source or retained mask changed")
        pointer = {"schemaVersion": "sam_shadow_mask_receipt_v1", "matchId": match_id,
            "generationId": shadow["generationId"], "sourceSha256": shadow["sourceSha256"],
            "requestDigest": shadow["requestDigest"], "jobId": job.job_id,
            "jobReceiptDigest": hashlib.sha256(canonical_json_bytes(receipt.to_mapping())).hexdigest(),
            "resultDigest": output.completion.result_sha256,
            "maskArtifactDigest": mask_digest, "maskOutputDigest": mask.outputDigest,
            "executionClass": mask.executionClass, "status": mask.status,
            "releaseQualification": "cpu_contract_only", "qualityAccepted": False}
        storage.save_analysis_artifact(match_id, "sam_shadow_mask", pointer)
        return pointer


def current_shadow_mask_overlay(storage, match_id: str, generation_id: str, frame_id: int) -> dict:
    """Read a retained mask only while its source, generation, and rights remain current."""
    from .remote_contracts import MAX_SEGMENTATION_RESULT_BYTES
    from .segmentation import MaskResult
    from .workbench.artifacts import ArtifactStore

    with storage._generation_lock(match_id):
        if storage.current_generation(match_id).generationId != generation_id:
            raise ValueError("stale mask generation")
        match = storage.get_match(match_id)
        if match.inputMode != "video" or not match.config.rights.cloudPermission \
                or match.config.rights.processingScope == "local_only":
            raise FileNotFoundError("review mask unavailable")
        try:
            pointer = storage.load_analysis_artifact(match_id, "sam_shadow_mask")
        except FileNotFoundError:
            raise FileNotFoundError("review mask unavailable") from None
        if pointer.get("schemaVersion") != "sam_shadow_mask_receipt_v1" \
                or pointer.get("matchId") != match_id or pointer.get("generationId") != generation_id \
                or pointer.get("sourceSha256") != storage.source_sha256(match_id) \
                or pointer.get("qualityAccepted") is not False:
            raise FileNotFoundError("review mask unavailable")
        try:
            raw = ArtifactStore(storage.storage_root / "artifacts").get(
                pointer["maskArtifactDigest"], namespace="segmentation",
                max_bytes=MAX_SEGMENTATION_RESULT_BYTES)
            mask = MaskResult.model_validate_json(raw)
        except (KeyError, ValueError):
            raise ValueError("retained review mask is invalid") from None
        if mask.sourceSha256 != pointer["sourceSha256"] \
                or mask.requestDigest != pointer["requestDigest"] \
                or mask.outputDigest != pointer["maskOutputDigest"] \
                or mask.executionClass != pointer["executionClass"] \
                or mask.status != pointer["status"]:
            raise ValueError("retained review mask identity changed")
        frame = next((item for item in mask.frames if item.frameId == frame_id), None)
        if frame is None:
            raise FileNotFoundError("review mask frame unavailable")
        tracks = {item.objectId: item.trackId for item in mask.objects}
        return {"schemaVersion": "mask_overlay_v1", "matchId": match_id,
            "generationId": generation_id, "sourceSha256": mask.sourceSha256,
            "sourceFrameId": frame_id, "ptsSeconds": frame.ptsSeconds,
            "width": mask.width, "height": mask.height,
            "qualification": "review_only", "executionClass": mask.executionClass,
            "masks": [{"objectId": item.objectId, "trackId": tracks[item.objectId], "rle": item.rle}
                for item in mask.masks if item.sourceFrameId == frame_id]}


def _validate_sam_release(root: Path, job, receipt, segmentation: SegmentationRequest) -> dict:
    """Bind a distinct SAM release declaration to sealed files and request identity."""
    from .remote_contracts import confined_path, load_canonical_json

    request_release = job.config.get("samRelease")
    manifest = load_canonical_json(confined_path(root, "release/sam-manifest.json"))
    evidence = load_canonical_json(confined_path(root, "release/sam-evidence.json"))
    expected = {"schemaVersion", "sourceCommit", "upstreamCommit", "imageDigest",
        "modelDigest", "workerDigest", "checkpointDigest", "sourceArchiveDigest"}
    if not isinstance(manifest, dict) or set(manifest) != expected \
            or manifest["schemaVersion"] != "sam_shadow_release_v1" \
            or not isinstance(evidence, dict) or set(evidence) != {"schemaVersion", "qualification"} \
            or evidence["schemaVersion"] != "sam_shadow_evidence_v1" \
            or evidence["qualification"] != "cpu_contract_only" \
            or not isinstance(request_release, Mapping) \
            or set(request_release) != {"imageDigest", "upstreamCommit"}:
        raise ValueError("SAM release identity is invalid")
    if not all(isinstance(manifest[key], str) and re.fullmatch(r"[a-f0-9]{64}", manifest[key])
               for key in ("imageDigest", "modelDigest", "workerDigest", "checkpointDigest", "sourceArchiveDigest")) \
            or not all(isinstance(manifest[key], str) and re.fullmatch(r"[a-f0-9]{40}", manifest[key])
               for key in ("sourceCommit", "upstreamCommit")) \
            or manifest["modelDigest"] != segmentation.modelDigest \
            or manifest["workerDigest"] != segmentation.workerDigest \
            or manifest["checkpointDigest"] != segmentation.checkpointDigest \
            or manifest["sourceCommit"] != receipt.source_commit \
            or request_release != {"imageDigest": manifest["imageDigest"],
                "upstreamCommit": manifest["upstreamCommit"]}:
        raise ValueError("SAM release identity is invalid")
    by_path = {entry.relative_path.as_posix(): entry for entry in receipt.files}
    expected_paths = {"source/source.tar", "release/sam-manifest.json",
        "release/sam-evidence.json", "models/sam-worker.bin",
        "inputs/window/window.json", "inputs/checkpoint.bin",
        "inputs/segmentation-request.json", "job-request.json"}
    expected_paths.update(f"inputs/window/{index}.png" for index in range(len(segmentation.frames)))
    if set(by_path) != expected_paths:
        raise ValueError("SAM release contains an undeclared file")
    if by_path["release/sam-manifest.json"].sha256 != receipt.manifest_sha256 \
            or by_path["release/sam-evidence.json"].sha256 != receipt.evidence_sha256 \
            or by_path["source/source.tar"].sha256 != manifest["sourceArchiveDigest"] \
            or by_path["models/sam-worker.bin"].sha256 != manifest["workerDigest"]:
        raise ValueError("SAM release artifact identity mismatch")
    return manifest


def seal_shadow_job(storage, root: Path, shadow: dict, *, release_root: Path):
    """Seal staged schema-2 inputs with separate SAM release files; dispatch stays closed."""
    from .remote_contracts import (JobReceipt, JobRequest, canonical_json_bytes,
        load_canonical_json)
    from .remote_worker import _copy_regular_file, _entry

    root, release_root = Path(root), Path(release_root)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir() \
            or not release_root.is_absolute() or release_root.is_symlink() or not release_root.is_dir() \
            or shadow.get("schemaVersion") != 2:
        raise ValueError("SAM staging or release root is invalid")
    def check_current():
        if storage.current_generation(shadow["matchId"]).generationId != shadow["generationId"]:
            raise ValueError("SAM shadow generation changed before sealing")
        match = storage.get_match(shadow["matchId"])
        if match.inputMode != "video" or not match.config.rights.cloudPermission \
                or match.config.rights.processingScope == "local_only":
            raise ValueError("SAM shadow rights changed before sealing")
        if storage.source_sha256(shadow["matchId"]) != shadow["sourceSha256"]:
            raise ValueError("SAM shadow source changed before sealing")
    check_current()
    segmentation = validate_sealed_shadow_request(root / "inputs/segmentation-request.json", shadow)
    validate_sam_source_window(root / "inputs/window", segmentation)
    source = release_root / "source.tar"
    manifest_source = release_root / "sam-manifest.json"
    evidence_source = release_root / "sam-evidence.json"
    worker = release_root / "worker.bin"
    manifest = load_canonical_json(manifest_source)
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != "sam_shadow_release_v1" \
            or manifest.get("modelDigest") != segmentation.modelDigest \
            or manifest.get("workerDigest") != segmentation.workerDigest \
            or manifest.get("checkpointDigest") != segmentation.checkpointDigest:
        raise ValueError("SAM release does not match staged model inputs")
    for name in ("source", "release", "models", "sealed", "job-request.json"):
        if (root / name).exists() or (root / name).is_symlink():
            raise ValueError("SAM job output path is occupied")
    try:
        for name in ("source", "release", "models", "sealed"):
            (root / name).mkdir(mode=0o700)
        fixed = ((source, "source/source.tar"), (manifest_source, "release/sam-manifest.json"),
            (evidence_source, "release/sam-evidence.json"), (worker, "models/sam-worker.bin"))
        for source_path, relative in fixed:
            _copy_regular_file(source_path, root / relative, maximum_bytes=512 * 1024**2)
        input_files = [("runtime_artifact", f"inputs/window/{index}.png")
            for index in range(len(segmentation.frames))]
        input_files += [("runtime_artifact", "inputs/checkpoint.bin"),
            ("runtime_artifact", "inputs/segmentation-request.json")]
        config = {"jobKind": "segmentation_shadow", "rights": {"cloudPermission": True,
            "processingScope": "local_plus_burst"}, "shadowSegmentation": shadow,
            "samRelease": {"imageDigest": manifest["imageDigest"],
                "upstreamCommit": manifest["upstreamCommit"]}}
        job = JobRequest(1, "sam-" + shadow["jobIdentity"], shadow["matchId"],
            PurePosixPath("sealed/job-receipt.json"), PurePosixPath("inputs/window/window.json"), config)
        (root / "job-request.json").write_bytes(canonical_json_bytes(job.to_mapping()))
        paths = (("source_archive", "source/source.tar"),
            ("manifest", "release/sam-manifest.json"),
            ("evidence", "release/sam-evidence.json"),
            ("runtime_artifact", "models/sam-worker.bin"),
            ("input_video", "inputs/window/window.json"), *input_files,
            ("job_request", "job-request.json"))
        entries = tuple(_entry(role, root, PurePosixPath(path)) for role, path in paths)
        by_role = {entry.role: entry for entry in entries if entry.role != "runtime_artifact"}
        receipt = JobReceipt(1, manifest["sourceCommit"], by_role["manifest"].sha256,
            by_role["evidence"].sha256, by_role["job_request"].sha256,
            {"jobKind": "segmentation_shadow", "modelAlias": segmentation.modelAlias,
             "executionMode": segmentation.executionMode, "precision": segmentation.precision}, entries)
        (root / job.receipt_path).write_bytes(canonical_json_bytes(receipt.to_mapping()))
        load_sealed_shadow_bundle(root)
        check_current()
        return job, receipt
    except Exception:
        try:
            for name in ("source", "release", "models", "sealed"):
                if (root / name).exists():
                    shutil.rmtree(root / name)
            (root / "job-request.json").unlink(missing_ok=True)
        except Exception:
            raise RuntimeError("SAM seal cleanup could not be confirmed") from None
        raise


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
    from .workbench.media import FfmpegProbe, verified_source_pts_index
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
    try:
        verified_source_pts_index(probe, source, policy,
            time_base=Fraction(media_identity.timeBaseNum, media_identity.timeBaseDen),
            expected={item.frameId: item.ptsSeconds for item in request.frames},
            timeout=timeout, cancelled=cancellation_requested,
            mismatch_message="shadow source frame PTS mismatch")
    except ValueError as exc:
        if cancellation_requested():
            raise ValueError("shadow job cancelled during preflight") from exc
        raise
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


def stage_shadow_inputs(storage, match_id: str, generation_id: str, payload: dict, *,
                        checkpoint_path: Path, approved_model_digest: str,
                        approved_worker_digest: str, approved_crop_digest: str,
                        deadline_seconds: float, workspace: Path,
                        cancelled: bool | Callable[[], bool] = False) -> tuple[Path, dict]:
    """Stage current, sealed SAM inputs; a separate SAM release proof is needed for dispatch."""
    from .remote_worker import _copy_regular_file

    started = monotonic()
    admitted = preflight_shadow_window(storage, match_id, generation_id, payload,
        checkpoint_path=checkpoint_path, approved_model_digest=approved_model_digest,
        approved_worker_digest=approved_worker_digest, approved_crop_digest=approved_crop_digest,
        deadline_seconds=deadline_seconds, cancelled=cancelled)
    request = SegmentationRequest.model_validate_json(json.dumps(payload))
    workspace = Path(workspace)
    if not workspace.is_absolute() or workspace.is_symlink() or not workspace.is_dir():
        raise ValueError("shadow input workspace is unavailable")
    root = Path(tempfile.mkdtemp(prefix="sam-inputs-", dir=workspace))
    os.chmod(root, 0o700)
    try:
        inputs = root / "inputs"
        inputs.mkdir(mode=0o700)
        remaining = deadline_seconds - (monotonic() - started)
        if remaining <= 0:
            raise ValueError("shadow job deadline expired during staging")
        window, _ = stage_sam_source_window(storage.get_match_input_path(match_id), request,
            inputs, timeout_seconds=remaining)
        os.replace(window, inputs / "window")
        checkpoint_identity = _copy_regular_file(Path(checkpoint_path),
            inputs / "checkpoint.bin", maximum_bytes=16 * 1024**3)
        if checkpoint_identity.sha256 != admitted["checkpointDigest"]:
            raise ValueError("shadow checkpoint changed during staging")
        (inputs / "segmentation-request.json").write_bytes(json.dumps(
            request.model_dump(mode="json"), sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode())
        if (cancelled() if callable(cancelled) else cancelled):
            raise ValueError("shadow job cancelled during staging")
        if monotonic() - started >= deadline_seconds:
            raise ValueError("shadow job deadline expired during staging")
        if storage.current_generation(match_id).generationId != generation_id:
            raise ValueError("stale shadow generation after staging")
        match = storage.get_match(match_id)
        if match.inputMode != "video" or not match.config.rights.cloudPermission \
                or match.config.rights.processingScope == "local_only":
            raise ValueError("source rights changed during shadow staging")
        if storage.source_sha256(match_id) != admitted["sourceSha256"]:
            raise ValueError("shadow source changed during staging")
        validate_sam_source_window(inputs / "window", request)
        shadow = {key: admitted[key] for key in ("matchId", "generationId", "requestDigest",
            "sourceSha256", "checkpointDigest", "deadlineSeconds")}
        shadow.update(schemaVersion=2,
            windowDigest=stream_sha256(inputs / "window/window.json").sha256)
        shadow["jobIdentity"] = digest({key: shadow[key] for key in (
            "matchId", "generationId", "requestDigest", "checkpointDigest", "windowDigest")})
        return root, shadow
    except Exception:
        try:
            shutil.rmtree(root)
        except Exception:
            raise RuntimeError("shadow input cleanup could not be confirmed") from None
        raise
