"""Remote-result snapshot, publication, and rollback persistence."""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path

_REMOTE_RESULT_FILENAMES = (
    "accepted_match_state.json",
    "analytics.json",
    "ball_pipeline_trace.json",
    "ball_truth_layers.json",
    "decode_anchors.json",
    "events.json",
    "four_rates.json",
    "tactical_report.json",
    "drills.json",
    "frames.json",
    "input_video_identity.json",
    "ownership_publication.json",
    "raw_rows.json",
    "recovery_debug.json",
    "recovery_profile_matrix.json",
)

_COPY_CHUNK_BYTES = 64 * 1024


def _open_regular_file(path: Path, flags: int = os.O_RDONLY) -> int:
    descriptor = -1
    try:
        descriptor = os.open(
            path,
            flags
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
            0o600,
        )
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError
        return descriptor
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        raise


def _copy_to_snapshot(source: Path, destination: Path) -> tuple[int, tuple[int, int, int]]:
    source_fd = snapshot_fd = -1
    try:
        source_fd = _open_regular_file(source)
        before = os.fstat(source_fd)
        snapshot_fd = _open_regular_file(
            destination,
            os.O_RDWR | os.O_CREAT | os.O_EXCL,
        )
        copied = 0
        while chunk := os.read(source_fd, _COPY_CHUNK_BYTES):
            copied += len(chunk)
            view = memoryview(chunk)
            while view:
                written = os.write(snapshot_fd, view)
                if written <= 0:
                    raise OSError
                view = view[written:]
        after = os.fstat(source_fd)
        named = os.stat(source, follow_symlinks=False)
        identity = (before.st_dev, before.st_ino, before.st_size)
        if (
            not stat.S_ISREG(named.st_mode)
            or (after.st_dev, after.st_ino, after.st_size) != identity
            or (named.st_dev, named.st_ino, named.st_size) != identity
            or copied != before.st_size
        ):
            raise OSError
        os.fsync(snapshot_fd)
        snapshot = os.fstat(snapshot_fd)
        return snapshot_fd, (snapshot.st_dev, snapshot.st_ino, snapshot.st_size)
    except Exception:
        if snapshot_fd >= 0:
            os.close(snapshot_fd)
        destination.unlink(missing_ok=True)
        raise
    finally:
        if source_fd >= 0:
            os.close(source_fd)


def _restore_snapshot(
    source: Path,
    source_fd: int,
    identity: tuple[int, int, int],
    destination: Path,
) -> None:
    opened = os.fstat(source_fd)
    if (
        not stat.S_ISREG(opened.st_mode)
        or (opened.st_dev, opened.st_ino, opened.st_size) != identity
    ):
        raise OSError
    try:
        named = os.stat(source, follow_symlinks=False)
        if (
            stat.S_ISREG(named.st_mode)
            and (named.st_dev, named.st_ino, named.st_size) == identity
        ):
            os.replace(source, destination)
            restored = os.stat(destination, follow_symlinks=False)
            if (
                stat.S_ISREG(restored.st_mode)
                and (restored.st_dev, restored.st_ino, restored.st_size) == identity
            ):
                return
    except OSError:
        pass

    temporary_fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.remote-restore-",
        dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        os.lseek(source_fd, 0, os.SEEK_SET)
        copied = 0
        while chunk := os.read(source_fd, _COPY_CHUNK_BYTES):
            copied += len(chunk)
            view = memoryview(chunk)
            while view:
                written = os.write(temporary_fd, view)
                if written <= 0:
                    raise OSError
                view = view[written:]
        after = os.fstat(source_fd)
        if (
            not stat.S_ISREG(after.st_mode)
            or (after.st_dev, after.st_ino, after.st_size) != identity
            or copied != identity[2]
        ):
            raise OSError
        os.fsync(temporary_fd)
        temporary_identity = os.fstat(temporary_fd)
        os.close(temporary_fd)
        temporary_fd = -1
        os.replace(temporary, destination)
        restored = os.stat(destination, follow_symlinks=False)
        if (
            not stat.S_ISREG(restored.st_mode)
            or (restored.st_dev, restored.st_ino, restored.st_size)
            != (
                temporary_identity.st_dev,
                temporary_identity.st_ino,
                temporary_identity.st_size,
            )
        ):
            raise OSError
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    finally:
        if temporary_fd >= 0:
            os.close(temporary_fd)


class _RemoteResultStorageMixin:
    @contextmanager
    def remote_result_import(self, match_id: str) -> Iterator[None]:
        self.generations.prepare(match_id)
        with self.generations.guard(match_id, "review", exclusive=True), self.generations.guard(match_id, "lifetime"):
            with self.generations.deferred_publication(match_id):
                with self._remote_result_import_backups(match_id):
                    yield

    @contextmanager
    def _remote_result_import_backups(self, match_id: str) -> Iterator[None]:
        """Restore owned football outputs and match metadata if import fails."""

        match_dir = self._match_dir(match_id)
        with self._connect() as connection:
            match_row = connection.execute(
                "SELECT status, config_json, requires_team_selection, team_clusters_json, updated_at "
                "FROM matches WHERE id = ?",
                (match_id,),
            ).fetchone()
        if match_row is None:
            raise KeyError(match_id)

        temporary = Path(tempfile.mkdtemp(prefix=".remote-import-", dir=self.storage_root))
        snapshot = temporary / "snapshot"
        snapshot.mkdir()
        snapshots: dict[str, tuple[int, tuple[int, int, int]]] = {}

        def cleanup_temporary() -> None:
            try:
                shutil.rmtree(temporary)
                if temporary.exists():
                    raise OSError
            except Exception:
                raise RuntimeError(
                    "remote result rollback cleanup could not be confirmed"
                ) from None

        def restore() -> None:
            try:
                for filename in _REMOTE_RESULT_FILENAMES:
                    destination = match_dir / filename
                    retained = snapshots.get(filename)
                    if retained is not None:
                        _restore_snapshot(
                            snapshot / filename,
                            retained[0],
                            retained[1],
                            destination,
                        )
                    else:
                        destination.unlink(missing_ok=True)
                with self._connect() as connection:
                    connection.execute(
                        """
                        UPDATE matches
                        SET status = ?, config_json = ?, requires_team_selection = ?, team_clusters_json = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            match_row["status"],
                            match_row["config_json"],
                            match_row["requires_team_selection"],
                            match_row["team_clusters_json"],
                            match_row["updated_at"],
                            match_id,
                        ),
                    )
            except Exception:
                raise RuntimeError(
                    "remote result rollback could not be confirmed"
                ) from None

        try:
            try:
                for filename in _REMOTE_RESULT_FILENAMES:
                    source = match_dir / filename
                    try:
                        source.lstat()
                    except FileNotFoundError:
                        continue
                    snapshots[filename] = _copy_to_snapshot(
                        source, snapshot / filename
                    )
            except Exception:
                cleanup_temporary()
                raise RuntimeError(
                    "remote result snapshot could not be confirmed"
                ) from None
            try:
                yield
            except BaseException:
                restore()
                cleanup_temporary()
                raise
            try:
                cleanup_temporary()
            except Exception:
                restore()
                raise
        finally:
            for descriptor, _identity in snapshots.values():
                os.close(descriptor)

    @contextmanager
    def remote_cost_unsettled(self) -> Iterator[None]:
        previous = self._remote_cost_unsettled
        self._remote_cost_unsettled = True
        try:
            yield
        finally:
            self._remote_cost_unsettled = previous
