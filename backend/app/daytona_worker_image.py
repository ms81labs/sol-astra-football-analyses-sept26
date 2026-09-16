"""Bounded source context for the shared Daytona worker image."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from typing import Any, Iterator


MAX_CONTEXT_MEMBER_BYTES = 2 * 1024 * 1024
MAX_CONTEXT_TOTAL_BYTES = 4 * 1024 * 1024
WORKER_CONTEXT_MEMBERS = (
    "lap.py",
    "backend/__init__.py", "backend/run_guerilla.py", "backend/pitch_detector.py",
    "backend/app/__init__.py", "backend/app/analytics.py", "backend/app/edge_share_repair.py",
    "backend/app/edge_share_repair_profiles.py", "backend/app/gpu_worker.py",
    "backend/app/homography_utils.py", "backend/app/processor.py", "backend/app/proof_runtime.py",
    "backend/app/release_manifest.py", "backend/app/remote_contracts.py",
    "backend/app/runtime_options.py", "backend/app/schemas.py", "backend/app/storage.py",
    "backend/app/team_classification.py", "backend/app/video_pipeline.py",
    "backend/release/v7.3.json", "backend/daytona_worker/requirements.lock",
)


class WorkerImageError(RuntimeError):
    pass


def _open_regular(path: Path) -> int:
    if not path.is_absolute():
        raise WorkerImageError("worker context source is unsafe")
    current = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:-1]:
            following = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            os.close(current); current = following
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise WorkerImageError("worker context source is unsafe")
        return descriptor
    except WorkerImageError:
        raise
    except Exception:
        raise WorkerImageError("worker context source is unsafe") from None
    finally:
        os.close(current)


def _copy_context_member(root: Path, context: Path, relative: str, total: int) -> int:
    source = root / relative
    descriptor = output = -1
    try:
        before = source.stat(follow_symlinks=False)
        descriptor = _open_regular(source)
        opened = os.fstat(descriptor)
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise WorkerImageError("worker context source changed")
        destination = context / relative
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        output = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        size = 0
        while chunk := os.read(descriptor, 64 * 1024):
            size += len(chunk)
            if size > MAX_CONTEXT_MEMBER_BYTES or total + size > MAX_CONTEXT_TOTAL_BYTES:
                raise WorkerImageError("worker context is not bounded")
            view = memoryview(chunk)
            while view:
                written = os.write(output, view)
                if written <= 0:
                    raise WorkerImageError("worker context copy failed")
                view = view[written:]
        after = source.stat(follow_symlinks=False)
        if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) != (
            opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns
        ):
            raise WorkerImageError("worker context source changed")
        return total + size
    finally:
        for handle in (output, descriptor):
            if handle >= 0:
                os.close(handle)


@contextmanager
def worker_context(repo_root: Path) -> Iterator[Path]:
    context = Path(tempfile.mkdtemp(prefix="daytona-worker-context-"))
    os.chmod(context, 0o700)
    try:
        total = 0
        for relative in WORKER_CONTEXT_MEMBERS:
            total = _copy_context_member(repo_root, context, relative, total)
        yield context
    finally:
        shutil.rmtree(context)


def worker_context_sha256(context: Path) -> str:
    identities = []
    for relative in WORKER_CONTEXT_MEMBERS:
        path = context / relative
        descriptor = _open_regular(path)
        try:
            opened = os.fstat(descriptor)
            digest = hashlib.sha256()
            size = 0
            while chunk := os.read(descriptor, 64 * 1024):
                size += len(chunk)
                digest.update(chunk)
            after = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns
            ):
                raise WorkerImageError("worker context changed while hashing")
        finally:
            os.close(descriptor)
        if size != opened.st_size or size > MAX_CONTEXT_MEMBER_BYTES:
            raise WorkerImageError("worker context is not bounded")
        identities.append({"path": relative, "sha256": digest.hexdigest(), "sizeBytes": size})
    encoded = (json.dumps(identities, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return hashlib.sha256(encoded).hexdigest()


def repository_worker_context_sha256(repo_root: Path) -> str:
    with worker_context(repo_root) as context:
        return worker_context_sha256(context)


def worker_image_factory(sdk: Any, repo_root: Path, digest_callback: Any = None):
    @contextmanager
    def build():
        dockerfile = (repo_root / "backend/daytona_worker/Dockerfile").read_text(encoding="utf-8").splitlines()
        with worker_context(repo_root) as context:
            digest = worker_context_sha256(context)
            image = sdk.Image.base(dockerfile[0].removeprefix("FROM ")).dockerfile_commands(
                dockerfile[1:], context_dir=str(context)
            )
            yield image
            if worker_context_sha256(context) != digest:
                raise WorkerImageError("worker context changed while in use")
            if digest_callback is not None:
                digest_callback(digest)
    return build
