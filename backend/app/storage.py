from __future__ import annotations

import json
import logging
from contextlib import contextmanager
import hashlib
import os
import shutil as shutil
import sqlite3
import stat
import tempfile
import threading
import uuid
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, TextIO


from .storage_jobs import (
    AdmissionOutcomeUncertainError as AdmissionOutcomeUncertainError,
    JobCancellationRequested as JobCancellationRequested,
    _JobStorageMixin,
)

from .storage_remote import _RemoteResultStorageMixin
from .storage_calibration import _CalibrationStorageMixin
from .storage_identity import _IdentityStorageMixin

from .schemas import (
    BallOwnership,
    ColorClusterSummary,
    CreateAnnotationRequest,
    CreateIssueRequest,
    DetectedEvent,
    FormationSegment,
    FrameData,
    MatchConfig,
    MatchRecord,
    MatchSummary,
    MatchIssueRecord,
    ReviewBundle,
    ShotAnalytics,
    TacticalAnnotationRecord,
)


LOGGER = logging.getLogger(__name__)


_COPY_CHUNK_BYTES = 64 * 1024
_UPLOAD_CHUNK_BYTES = 1024 * 1024


class UploadTooLargeError(ValueError):
    pass


class ReviewBundleCorruptError(RuntimeError):
    pass


class StorageWriteOutcomeUncertain(OSError):
    pass


class StorageDeleteOutcomeUncertain(OSError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _ClosingConnection:
    """sqlite3 connections do not close on context exit; this wrapper does."""

    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection
        self._closed = False

    def __getattr__(self, name: str):
        return getattr(self._connection, name)

    def __enter__(self) -> "_ClosingConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        try:
            if exc_type is None:
                self._connection.commit()
            else:
                try:
                    self._connection.rollback()
                except Exception:
                    LOGGER.warning("storage transaction rollback failed")
        finally:
            self.close()
        return False

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._connection.close()


def _generation_writer(method):
    from functools import wraps

    @wraps(method)
    def guarded(self, match_id, *args, **kwargs):
        self.generations.prepare(match_id)
        with self.generations.guard(match_id, "review", exclusive=True), self.generations.guard(match_id, "lifetime"):
            try:
                self.generations.resolve(match_id)
            except FileNotFoundError:
                pass  # Known pre-generation compatibility writer, not GET migration.
            return method(self, match_id, *args, **kwargs)
    return guarded


def _generation_reader(method):
    """Keep all derived input/eligibility reads on one immutable generation."""
    from contextlib import ExitStack
    from functools import wraps

    @wraps(method)
    def guarded(self, match_id, *args, **kwargs):
        with ExitStack() as stack:
            try:
                stack.enter_context(self.generation_snapshot(match_id, generation_id=kwargs.get("generation_id")))
            except FileNotFoundError:
                pass  # Preserve the method's documented pre-processing outcome.
            return method(self, match_id, *args, **kwargs)
    return guarded


class Storage(_IdentityStorageMixin, _CalibrationStorageMixin, _RemoteResultStorageMixin, _JobStorageMixin):
    def __init__(self, storage_root: Path):
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        from .workbench.hashing import HashCache

        self.hash_cache = HashCache(self.storage_root)
        self.db_path = self.storage_root / "guerilla.sqlite3"
        # ponytail: per-instance only; use a cross-process lock if multiple Storage instances mutate these files.
        self._annotation_issue_lock = threading.Lock()
        # ponytail: per-instance only; use a cross-process lock if multiple API workers mutate bundles.
        self._review_bundle_lock = threading.Lock()
        from .storage_review import ReviewStorage

        self._review_storage = ReviewStorage(
            self,
            corrupt_error=ReviewBundleCorruptError,
            uncertain_delete_error=StorageDeleteOutcomeUncertain,
        )
        from .storage_corrections import CorrectionStorage

        self._correction_storage = CorrectionStorage(self)
        # ponytail: per-instance config serialization; use per-match cross-process locks for multiple API workers.
        self.config_update_lock = threading.Lock()
        self._remote_cost_unsettled = False
        from .generations import GenerationStore
        self.generations = GenerationStore(self)
        self._generation_recovery_errors = {}
        self._initialize()
        from .workbench.jobs import DurableJobLedger

        self.job_ledger = DurableJobLedger(db_path=self.db_path)
        self._initialise_generation_stores()
        self._recover_pending_reviews()

    def _recover_pending_reviews(self) -> None:
        matches = self.storage_root / "matches"
        if not matches.exists():
            return
        directories = [
            directory
            for directory in matches.iterdir()
            if directory.name not in self._generation_recovery_errors and directory.is_dir() and (directory / "corrections.json").is_file()
            and any(
                item.get("applyState") in {"committed", "applying"}
                for item in (self._read_json(directory / "corrections.json").get("items") or [])
            )
        ]
        if not directories:
            return
        from .review_service import ReviewService

        service = ReviewService(self)
        for directory in directories:
            service.apply_pending(directory.name)

    def _initialise_generation_stores(self) -> None:
        from .generations import GenerationRecoveryRequired
        root = self.storage_root / "matches"
        for directory in root.iterdir() if root.exists() else ():
            if not directory.is_dir():
                continue
            try:
                self.recover_generations(directory.name)
                self._complete_generations(directory.name)
            except (OSError, GenerationRecoveryRequired) as exc:
                self._generation_recovery_errors[directory.name] = str(exc)

    def recover_generations(self, match_id: str, *, migrate: bool = True) -> dict:
        receipt = self.generations.recover(match_id, migrate=migrate)
        self._generation_recovery_errors.pop(match_id, None)
        return receipt

    def retain_generations(self, match_id: str, **options) -> dict:
        return self.generations.retention(match_id, **options)

    def close(self) -> None:
        try:
            connection = self._open_connection()
            try:
                connection.execute("PRAGMA wal_checkpoint(PASSIVE)")
            finally:
                connection.close()
        except Exception:
            LOGGER.warning("storage checkpoint cleanup failed")
        ledger = getattr(self, "job_ledger", None)
        if ledger is not None and hasattr(ledger, "close"):
            ledger.close()

    def _open_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _connect(self) -> _ClosingConnection:
        return _ClosingConnection(self._open_connection())

    def _initialize(self) -> None:
        with self._connect() as connection:
            # Serialize schema discovery and migration across startup processes.
            # BEGIN belongs inside executescript, which commits a pending transaction.
            connection.executescript(
                """
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS matches (
                    id TEXT PRIMARY KEY,
                    admission_token TEXT,
                    name TEXT NOT NULL,
                    input_mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    input_path TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    analytics_summary_json TEXT,
                    requires_team_selection INTEGER NOT NULL DEFAULT 0,
                    team_clusters_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    match_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress REAL NOT NULL,
                    message TEXT,
                    error TEXT,
                    runpod_run_id TEXT,
                    log_path TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(match_id) REFERENCES matches(id)
                );
                """
            )
            match_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(matches)").fetchall()
            }
            for column in ("analytical_generation_id", "semantic_config_revision"):
                if column not in match_columns:
                    connection.execute(f"ALTER TABLE matches ADD COLUMN {column} TEXT")
            if "admission_token" not in match_columns:
                connection.execute("ALTER TABLE matches ADD COLUMN admission_token TEXT")
            if "analytics_summary_json" not in match_columns:
                connection.execute("ALTER TABLE matches ADD COLUMN analytics_summary_json TEXT")
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS matches_admission_token_unique "
                "ON matches(admission_token) WHERE admission_token IS NOT NULL"
            )
            job_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
            }
            if "log_path" not in job_columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN log_path TEXT")
            if "runpod_run_id" not in job_columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN runpod_run_id TEXT")
            if "started_at" not in job_columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN started_at TEXT")
            if "completed_at" not in job_columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN completed_at TEXT")

    def _match_dir(self, match_id: str) -> Path:
        path = self.storage_root / "matches" / match_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_upload(self, filename: str, payload: bytes) -> Path:
        return self.save_upload_stream(filename, BytesIO(payload))

    def save_upload_stream(
        self,
        filename: str,
        stream: BinaryIO,
        max_bytes: int | None = None,
    ) -> Path:
        if max_bytes is not None and (type(max_bytes) is not int or max_bytes <= 0):
            raise ValueError("max_bytes must be a positive integer")
        upload_dir = self.storage_root / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        path = upload_dir / f"{uuid.uuid4().hex}_{Path(filename).name or 'upload.bin'}"
        temporary_fd, temporary_name = tempfile.mkstemp(prefix=".upload.", dir=upload_dir)
        temporary = Path(temporary_name)
        published = False
        try:
            handle = os.fdopen(temporary_fd, "wb")
            temporary_fd = -1
            with handle:
                total = 0
                while chunk := stream.read(_UPLOAD_CHUNK_BYTES):
                    total += len(chunk)
                    if max_bytes is not None and total > max_bytes:
                        raise UploadTooLargeError(
                            f"Upload exceeds maximum size of {max_bytes} bytes"
                        )
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            published = True
            directory_fd = os.open(
                upload_dir,
                os.O_RDONLY
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            return path
        except BaseException:
            if temporary_fd >= 0:
                try:
                    os.close(temporary_fd)
                except OSError:
                    pass
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            if published:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise

    def create_match(self, name: str, input_mode: str, original_filename: str, input_path: Path, config: MatchConfig) -> MatchRecord:
        match_id = uuid.uuid4().hex
        now = _utcnow().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO matches (id, name, input_mode, status, original_filename, input_path, config_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    name,
                    input_mode,
                    "processing",
                    original_filename,
                    str(input_path),
                    config.model_dump_json(),
                    now,
                    now,
                ),
            )
        self.generations.prepare(match_id)
        return self.get_match(match_id)

    def update_match_status(
        self,
        match_id: str,
        *,
        status: str,
        requires_team_selection: bool = False,
        team_clusters: list[ColorClusterSummary] | None = None,
    ) -> MatchRecord:
        now = _utcnow().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE matches SET status = ?, requires_team_selection = ?, team_clusters_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    int(requires_team_selection),
                    json.dumps([cluster.model_dump(mode="json") for cluster in (team_clusters or [])]),
                    now,
                    match_id,
                ),
            )
        return self.get_match(match_id)

    def update_match_config(self, match_id: str, config: MatchConfig) -> MatchRecord:
        now = _utcnow().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE matches SET config_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (config.model_dump_json(), now, match_id),
            )
        return self.get_match(match_id)

    def get_match(self, match_id: str) -> MatchRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
        if row is None:
            raise KeyError(match_id)
        team_clusters = json.loads(row["team_clusters_json"] or "[]")
        return MatchRecord(
            id=row["id"],
            name=row["name"],
            inputMode=row["input_mode"],
            status=row["status"],
            originalFilename=row["original_filename"],
            config=self.generations.configuration(match_id, MatchConfig.model_validate_json(row["config_json"])),
            createdAt=datetime.fromisoformat(row["created_at"]),
            updatedAt=datetime.fromisoformat(row["updated_at"]),
            requiresTeamSelection=bool(row["requires_team_selection"]),
            teamClusters=[ColorClusterSummary.model_validate(item) for item in team_clusters],
        )

    def get_match_input_path(self, match_id: str) -> Path:
        with self._connect() as connection:
            row = connection.execute("SELECT input_path FROM matches WHERE id = ?", (match_id,)).fetchone()
        if row is None:
            raise KeyError(match_id)
        return Path(row["input_path"])

    def list_matches(self) -> list[MatchRecord]:
        with self._connect() as connection:
            rows = connection.execute("SELECT id FROM matches ORDER BY created_at DESC").fetchall()
        return [self.get_match(row["id"]) for row in rows]

    @_generation_writer
    def save_frames(self, match_id: str, frames: Iterable[FrameData]) -> None:
        if (self._match_dir(match_id) / "current_generation.json").exists():
            self._publish_replacement(match_id, frames=list(frames))
            return
        self._write_json_array(
            self._match_dir(match_id) / "frames.json",
            (frame.model_dump(mode="json") for frame in frames),
        )

    def save_raw_rows(self, match_id: str, rows: Iterable[dict]) -> None:
        self._write_json_array(self._match_dir(match_id) / "raw_rows.json", rows)

    def _video_ball_signal_summary(self, match_id: str, summary: MatchSummary, *, input_mode: str | None = None) -> MatchSummary:
        # ponytail: promote video trust only after a match-bound independent ball-label receipt exists.
        # Bulk listing already has this immutable, server-owned column. Reuse it
        # instead of opening one extra SQLite connection for every match.
        if input_mode is None:
            with self._connect() as connection:
                row = connection.execute("SELECT input_mode FROM matches WHERE id=?", (match_id,)).fetchone()
            if row is None:
                return summary  # Artifact-only record has no authoritative input mode.
            input_mode = row["input_mode"]
        if input_mode == "video" and summary.ballSignalStatus == "trusted":
            return summary.model_copy(update={
                "ballSignalStatus": "untrusted",
                "ballSignalMessage": "Ball detections have not been independently verified.",
            })
        return summary

    @_generation_writer
    def save_analytics(
        self,
        match_id: str,
        summary: MatchSummary,
        assignments: list[BallOwnership],
        formation_timeline: list[FormationSegment],
        shots: list[ShotAnalytics],
    ) -> None:
        summary = self._video_ball_signal_summary(match_id, summary)
        if not any(assignment.team in {"my_team", "enemy"} for assignment in assignments):
            summary = summary.model_copy(update={"possession": None})
        if (self._match_dir(match_id) / "current_generation.json").exists():
            self._publish_replacement(
                match_id,
                summary=summary,
                assignments=assignments,
                formation_timeline=formation_timeline,
                shots=shots,
            )
            return
        self._write_json(
            self._match_dir(match_id) / "analytics.json",
            {
                "summary": summary.model_dump(mode="json"),
                "ballAssignments": [assignment.model_dump(mode="json") for assignment in assignments],
                "formationTimeline": [segment.model_dump(mode="json") for segment in formation_timeline],
                "shots": [shot.model_dump(mode="json") for shot in shots],
            },
        )
        with self._connect() as connection:
            connection.execute(
                "UPDATE matches SET analytics_summary_json = ? WHERE id = ?",
                (summary.model_dump_json(), match_id),
            )

    @_generation_writer
    def save_events(self, match_id: str, events: list[DetectedEvent]) -> None:
        if (self._match_dir(match_id) / "current_generation.json").exists():
            self._publish_replacement(match_id, events=events)
            return
        self._write_json(self._match_dir(match_id) / "events.json", [event.model_dump(mode="json") for event in events])

    def _publish_replacement(self, match_id: str, *, frames=None, summary=None,
                             assignments=None, formation_timeline=None, shots=None, events=None) -> None:
        with self.generations.guard(match_id, "review", exclusive=True):
            with self.generation_snapshot(match_id) as ref:
                manifest, _ = self.generations.manifest(match_id, ref.generationId)
                old_summary, old_assignments, old_formations, old_shots = self.load_analytics(match_id)
                config = manifest.effectiveConfig
                self.publish_generation(
                    match_id, frames=frames if frames is not None else self.load_frames(match_id),
                    summary=summary if summary is not None else old_summary,
                    assignments=assignments if assignments is not None else old_assignments,
                    formation_timeline=formation_timeline if formation_timeline is not None else old_formations,
                    shots=shots if shots is not None else old_shots,
                    events=events if events is not None else self.load_events(match_id),
                    correction_head=ref.correctionHead, calibration_revision=manifest.calibrationRevision,
                    calibration_data=manifest.calibrationData, effective_config=config,
                    expected_parent=ref.generationId, provenance=manifest)

    @contextmanager
    def _generation_lock(self, match_id: str):
        with self.generations.guard(match_id, "review", exclusive=True), self.generations.guard(match_id, "lifetime"), self.generations.guard(match_id, "publication", exclusive=True):
            yield

    def current_generation(self, match_id: str):
        with self.generation_snapshot(match_id) as ref:
            return ref

    @contextmanager
    def generation_snapshot(self, match_id: str, *, generation_id: str | None = None):
        with self.generations.snapshot(match_id, generation_id) as ref:
            yield ref

    def _current_generation_unlocked(self, match_id: str):
        return self.generations.resolve(match_id)

    def _complete_generations(self, match_id: str) -> dict[str, object]:
        """Explicit maintenance helper; never called by a routine reader."""
        from .generations import GenerationRecoveryRequired
        with self.generations.guard(match_id, "lifetime"):
            result = {}
            root = self.generations.root(match_id) / "generations"
            for directory in root.iterdir() if root.exists() else ():
                if directory.is_dir() and directory.name.startswith("gen_"):
                    try:
                        result[directory.name] = self.generations.verify(match_id, directory.name)[0]
                    except (OSError, GenerationRecoveryRequired):
                        continue
            return result

    def _import_legacy_generation(self, match_id: str):
        self.recover_generations(match_id)
        ref = self.current_generation(match_id)
        return self.generations.manifest(match_id, ref.generationId)[0]

    def publish_generation(self, match_id: str, **payload):
        return self.generations.publish(match_id, **payload)

    def _generation_layer_identities(self, match_id: str, *, calibration_revision: str | None,
                                     correction_head: str, observations=None, effective_config=None,
                                     identity_context=None, command_digest=None, calibration_data=None) -> dict[str, dict]:
        from .workbench.cache import DetectionIdentity, TrackingIdentity
        from .perception_identity import canonical_digest, envelope
        from .generations import semantic_config
        layers = {}
        # Sidecar declarations must reconstruct to their own digests and source.
        try:
            dp = self.load_analysis_artifact(match_id, "detection_identity")
            tp = self.load_analysis_artifact(match_id, "tracking_identity")
            detection = DetectionIdentity(**dp["components"])
            tracking = TrackingIdentity(DetectionIdentity(**tp["components"]["detection"]),
                                        tp["components"]["tracker_config_id"])
            source = observations["source"]["sha256"] if observations else None
            for name, identity, stored in (("detection", detection, dp), ("tracking", tracking, tp)):
                key = identity.digest()
                if (not key or stored.get("reusable") is not True or key != stored.get("digest")
                        or detection.source_sha256 != source):
                    key = None
                layers[name] = envelope(key, identity.components(), ["INPUT_IDENTITY_UNVERIFIED"])
        except (FileNotFoundError, KeyError, TypeError, ValueError):
            pass
        if not observations or observations.get("matchId") != match_id:
            return layers
        # This observed content can be reused only inside this match. It is not a
        # claim that an unqualified perception run matches a future inference key.
        observation = canonical_digest(observations)
        layers["observation"] = envelope(observation, observations)
        projection_inputs = {"observations": observation, "calibrationRevision": calibration_revision,
            "calibration": calibration_data, "coordinates": (effective_config or {}).get("coordinateConvention"),
            "algorithm": "c02-source-projection-v1"}
        projection = canonical_digest(projection_inputs)
        reviewed_inputs = {"projection": projection,
            "semanticConfig": semantic_config(effective_config or {}),
            "identityRevision": (identity_context or {}).get("identityRevision"),
            "commands": command_digest, "correctionHead": correction_head, "algorithm": "c02-materializer-v1"}
        reviewed = canonical_digest(reviewed_inputs) if command_digest and identity_context else None
        layers["projection"] = envelope(projection, projection_inputs)
        layers["reviewed"] = envelope(reviewed, reviewed_inputs, ["REVIEW_INPUT_IDENTITY_INCOMPLETE"])
        report_inputs = {"reviewed": reviewed, "task": "deterministic_summary", "schema": "match-summary-v1"}
        layers["report"] = envelope(canonical_digest(report_inputs) if reviewed else None,
                                    report_inputs, ["REVIEW_INPUT_IDENTITY_INCOMPLETE"])
        return layers

    def _publish_generation_unlocked(self, match_id: str, **payload):
        # Compatibility name; every writer still participates in the protocol.
        return self.generations.publish(match_id, **payload)

    @staticmethod
    def _review_test_fault(point: str) -> None:
        if os.environ.get("GA_TEST_FAULTS") == "1" and os.environ.get("GA_TEST_FAULT_POINT") == point:
            os._exit(1)

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(_COPY_CHUNK_BYTES), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _generation_payload_path(self, match_id: str, filename: str, generation_id: str | None = None) -> Path:
        """Compatibility path resolver; callers must hold generation_snapshot through use."""
        if filename not in {"frames.json", "events.json", "analytics.json", "summary.json", "shots.json", "config.json"}:
            raise ValueError("unsupported generation filename")
        with self.generation_snapshot(match_id, generation_id=generation_id) as ref:
            return self.generations.root(match_id) / "generations" / ref.generationId / filename

    def save_analysis_artifact(self, match_id: str, analysis_type: str, payload: dict) -> None:
        path = self._match_dir(match_id) / f"{analysis_type}.json"
        if analysis_type.endswith(".receipt") or analysis_type in {"worker_progress", "remote_worker_progress"}:
            self._write_json(path, payload)
            return
        previous_digest = self.hash_cache.identity(path).sha256 if path.exists() else "0" * 64
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        from .workbench.artifacts import ArtifactStore, write_alongside

        receipt = write_alongside(
            ArtifactStore(self.storage_root / "artifacts"),
            previous_digest=previous_digest,
            payload=encoded,
            namespace=analysis_type,
        )
        self._write_json(path, payload)
        receipt_path = self._match_dir(match_id) / "receipts" / f"{analysis_type}.json"
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json(receipt_path, receipt)

    def invalidate_coach_analysis(self, match_id: str) -> None:
        # C03: report freshness is derived from its source generation. Preserve
        # flat legacy narratives as historical/unverified rather than deleting them.
        return None

    def append_analysis_artifact_jsonl(self, match_id: str, analysis_type: str, payload: dict) -> None:
        path = self._match_dir(match_id) / f"{analysis_type}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":")))
            handle.write("\n")

    def load_frames(self, match_id: str, *, generation_id: str | None = None) -> list[FrameData]:
        payload = self.generations.payload(match_id, "frames.json", generation_id)
        return [FrameData.model_validate(item) for item in payload]

    def load_frames_page(
        self,
        match_id: str,
        *,
        after_frame: int | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> dict:
        from .workbench.repository import RepositoryAdapter

        return RepositoryAdapter().page_frames(
            self.load_frames(match_id),
            after_frame=after_frame,
            cursor=cursor,
            limit=limit,
        )

    def load_evidence_page(
        self,
        match_id: str,
        *,
        interval_start: float | None = None,
        interval_end: float | None = None,
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict:
        from .workbench.evidence import query_match_evidence

        from .report_contracts import digest
        with self.generation_snapshot(match_id) as generation:
            frames = self.load_frames(match_id, generation_id=generation.generationId)
            events = self.load_events(match_id, generation_id=generation.generationId)
            page = query_match_evidence(frames, events, interval_start=interval_start,
                interval_end=interval_end, cursor=cursor, limit=limit, match_id=match_id)
            result = page.model_dump(mode="json")
            result["generationId"] = generation.generationId
            for item in result["items"]:
                kind, _, local_id = item["evidenceId"].partition(":")
                ref = {"matchId": match_id, "generationId": generation.generationId,
                       "kind": kind, "localId": local_id}
                item["reference"] = ref
                # The legacy evidenceId remains for history/cursors only. New
                # factual submissions use this scoped reference or approved alias.
                item["reportAlias"] = ("ref_" + digest({"task": "tactical_report", **ref})
                    if item["reviewStatus"] not in {"rejected", "superseded"} and not item["supersededBy"] else None)
            return result

    def _corrections_path(self, match_id: str) -> Path:
        return self._correction_storage.path(match_id)

    def _load_correction_log(self, match_id: str):
        return self._correction_storage.load_log(match_id)

    def _save_correction_log(self, match_id: str, log) -> None:
        self._correction_storage.save_log(match_id, log)

    def submit_correction(
        self, match_id: str, *, kind: str, payload: dict | None = None,
        author: str = "analyst", expected_version: int | None = None,
        crash_before_commit: bool = False, base_generation: str | None = None,
        command_id: str | None = None, idempotency_key: str | None = None,
    ):
        from .review_service import ReviewService
        # The canonical service validates non-object inputs; do not coerce an
        # arbitrary iterable into a supposedly valid command dictionary.
        payload = {} if payload is None else payload
        return ReviewService(self).submit(
            match_id, kind=kind, payload=payload, author=author,
            expected_version=expected_version, base_generation=base_generation,
            crash_before_commit=crash_before_commit, command_id=command_id,
            idempotency_key=idempotency_key,
        )

    def recover_correction(self, match_id: str, correction_id: str):
        from .review_service import ReviewService

        return ReviewService(self).recover(match_id, correction_id)

    def undo_correction(self, match_id: str, correction_id: str, *, author: str = "analyst",
                        expected_version: int | None = None, base_generation: str | None = None,
                        command_id: str | None = None, idempotency_key: str | None = None):
        from .review_service import ReviewService

        return ReviewService(self).undo(match_id, correction_id, author=author,
                                        expected_version=expected_version, base_generation=base_generation,
                                        command_id=command_id, idempotency_key=idempotency_key)

    def list_corrections(self, match_id: str, *, state: str | None = None) -> list[dict]:
        return self._correction_storage.list_corrections(match_id, state=state)

    def _active_playlist_payloads(self, match_id: str) -> list[dict]:
        ref = self.current_generation(match_id)
        manifest, _ = self.generations.manifest(match_id, ref.generationId)
        included = set(manifest.includedCommandIds)
        corrections = [item for item in self.list_corrections(match_id)
                       if item.get("commandId", item.get("correctionId")) in included
                       and item.get("applyState") == "applied"]
        undone = {item.get("undoOf") for item in corrections if item.get("undoOf")}
        return [item["payload"] for item in corrections
                if item.get("kind") == "playlist_item" and not item.get("undoOf")
                and item.get("correctionId") not in undone and isinstance(item.get("payload"), dict)]

    def _event_review_snapshot(self, match_id: str, payload: dict) -> list[dict]:
        from .workbench.events import event_matches_review_payload

        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            return []
        previous: list[dict] = []
        for index, event in enumerate(events):
            if not event_matches_review_payload(event, payload, match_id=match_id, index=index):
                continue
            previous.append(
                {
                    "frameId": int(event.frameId),
                    "timestamp": event.timestamp,
                    "type": event.type,
                    "reviewStatus": event.reviewStatus,
                }
            )
        return previous

    def _apply_saved_correction(self, match_id: str, saved) -> None:
        if saved.kind in {"event_accept", "event_reject"}:
            from .workbench.events import apply_event_review

            try:
                events = self.load_events(match_id)
            except FileNotFoundError:
                return
            updated, _previous = apply_event_review(
                events,
                kind=saved.kind,
                payload=dict(saved.payload or {}),
                match_id=match_id,
            )
            self.save_events(match_id, updated)
            return
        if saved.kind == "team_mapping":
            self._apply_team_mapping(match_id, dict(saved.payload or {}))
            return
        if saved.kind == "identity_validate":
            self._recompute_identity_continuity(match_id, identity_continuous=True)
            return
        if saved.kind == "calibration":
            self._save_calibration_evaluation(match_id, dict((saved.payload or {}).get("evaluation") or {}))

    def _apply_team_mapping(self, match_id: str, payload: dict) -> None:
        if payload.get("swap") is not True:
            return
        from .processor import reprocess_video_match
        from .workbench.identity import apply_team_swap

        try:
            frames = self.load_frames(match_id)
        except FileNotFoundError:
            return
        self.save_frames(match_id, apply_team_swap(frames))
        reprocess_video_match(self, match_id)

    def _restore_event_review(self, match_id: str, previous: list[dict]) -> None:
        from .workbench.events import restore_event_review

        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            return
        self.save_events(match_id, restore_event_review(events, previous))

    def query_match_events(self, match_id: str, query_text: str, *, include_unknown: bool = False) -> dict:
        from .workbench.assistance import events_as_query_rows, execute_typed_query, parse_typed_query

        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            events = []
        query = parse_typed_query(query_text, include_unknown=include_unknown)
        hits = execute_typed_query(events_as_query_rows(events, match_id=match_id), query, match_id=match_id)
        return {
            "query": query.model_dump(mode="json"),
            "interpreted": query.interpreted,
            "unsupportedTerms": query.unsupportedTerms,
            "results": [hit.model_dump(mode="json") for hit in hits],
        }

    @_generation_reader
    def assemble_match_report(
        self,
        match_id: str,
        *,
        claimed_evidence_ids: list[str | dict] | None = None,
        narrative: dict | None = None,
        generation_id: str | None = None,
    ) -> dict:
        from .provider_gateway import ProviderGateway, validate_output
        from .report_contracts import validate_declared_references, deterministic_fallback
        from .settings import ProcessingSettings
        with self.generation_snapshot(match_id, generation_id=generation_id) as generation:
            package, _ = ProviderGateway(self, ProcessingSettings(), adapter_factory=None).build_evidence(
                match_id, generation.generationId, "tactical_report")
            reasons = []
            references = []
            if claimed_evidence_ids is not None:
                try:
                    references = validate_declared_references({"evidence": claimed_evidence_ids}, package)
                except (ValueError, TypeError):
                    reasons.append("FABRICATED_EVIDENCE")
            validated = validate_output(narrative, package) if narrative is not None else None
            if validated is not None and validated.grounding not in {"grounded", "referenced", "interpretive"}:
                reasons.extend(validated.reason_codes)
            accepted = not reasons
            return {"matchId": match_id, "generationId": generation.generationId,
                    "evidenceSelection": {"evidenceIds": references, "exclusions": reasons},
                    "factPackage": {"metrics": list(package.metrics), "events": list(package.events),
                                    "template": deterministic_fallback(package, tuple(reasons), failed=bool(reasons)),
                                    "inputEvidenceDigest": package.digest, "aliases": package.aliases},
                    "narrativeDraft": {"optional": True, "payload": validated.payload if validated and accepted else {},
                                       "separatedFromFacts": True},
                    "factualCheck": {"accepted": accepted, "reasonCodes": reasons},
                    "publication": {"accepted": accepted, "requiresAnalyst": True, "wholeMatchFrequency": False,
                                    "frequencyRequiresDenominator": True}}

    @_generation_reader
    def player_observations_for_match(self, match_id: str) -> dict:
        from .workbench.identity import player_observations, rows_from_frames

        identity = self._stored_identity_continuous(match_id)
        geometry = self._stored_calibration_accepted(match_id)
        result = player_observations(
            rows_from_frames(self.load_frames(match_id)),
            identity_continuous=identity and geometry,
        )
        return {**result, "identityContinuous": identity, "geometryEligible": geometry,
                "reasonCodes": ([] if identity else ["IDENTITY_DISCONTINUITY"]) +
                               ([] if geometry else ["CALIBRATION_UNAVAILABLE"])}

    def search_stored_library(self, query: str) -> dict:
        from .workbench.library import search_match_library

        matches = [
            {
                "id": match.id,
                "title": match.name,
                "name": match.name,
                "cameraProfile": match.config.cameraProfile,
                "inputMode": match.inputMode,
                "status": match.status,
            }
            for match in self.list_matches()
        ]
        return search_match_library(query=query, matches=matches)

    def classify_match_ownership(self, match_id: str) -> dict:
        from .workbench.ownership import classify_ownership

        frames = self.load_frames(match_id)
        if not frames:
            observation = classify_ownership(
                ball_visible=False,
                nearest_team=None,
                nearest_distance=None,
                relative_motion=None,
                persistence_frames=0,
                calibrated=False,
            )
            return observation.model_dump(mode="json")
        frame = frames[0]
        possession = frame.possession
        nearest_team = None
        nearest_distance = None
        if possession is not None and possession.team in {"my_team", "enemy"}:
            nearest_team = possession.team
            nearest_distance = possession.distance
        observation = classify_ownership(
            ball_visible=frame.ball is not None,
            nearest_team=nearest_team,
            nearest_distance=nearest_distance,
            relative_motion=None,
            persistence_frames=0,
            calibrated=False,
        )
        return observation.model_dump(mode="json")

    def publish_ownership_events(self, match_id: str) -> dict:
        from .workbench.events import propose_event
        from .workbench.ownership import OwnershipHysteresis, classify_ownership

        frames = self.load_frames(match_id)
        hysteresis = OwnershipHysteresis()
        states = []
        for frame in frames:
            possession = frame.possession
            nearest_team = possession.team if possession is not None and possession.team in {"my_team", "enemy"} else None
            if nearest_team is None and frame.myTeam:
                nearest_team = "my_team"
            observation = classify_ownership(
                ball_visible=frame.ball is not None,
                nearest_team=nearest_team,
                nearest_distance=possession.distance if possession is not None else None,
                relative_motion="stable" if nearest_team else None,
                persistence_frames=3 if nearest_team else 0,
                calibrated=False,
            )
            held = hysteresis.observe(observation.controllingTeam if observation.mode == "controlled_possession" else "unknown")
            payload = observation.model_dump(mode="json")
            payload["hysteresisTeam"] = held
            payload["timestamp"] = frame.timestamp
            payload["nearestIsNotControl"] = True
            states.append(payload)
        event = propose_event(family="turnover", release=None, receipt=None)
        published = {
            "nearestIsNotControl": True,
            "states": states,
            "eventsPublication": event.model_dump(mode="json"),
        }
        self.save_analysis_artifact(match_id, "ownership_publication", published)
        return published

    @_generation_reader
    def assemble_stored_match_package(self, match_id: str) -> dict:
        from .workbench.assistance import events_as_query_rows
        from .workbench.evidence import summarize_legacy_match
        from .workbench.package import assemble_match_package

        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            events = []
        frames = self.load_frames(match_id)
        summary, _, _, _ = self.load_analytics(match_id)
        controlled = sum(
            1
            for frame in frames
            if frame.possession is not None and frame.possession.team in {"my_team", "enemy"}
        )
        metrics = [
            metric.model_dump(mode="json")
            for metric in summarize_legacy_match(
                summary.model_dump(mode="json"),
                identity_continuous=self._stored_identity_continuous(match_id),
                calibration_accepted=self._stored_calibration_accepted(match_id),
                controlled_frames=controlled,
            )
        ]
        corrections = self.list_corrections(match_id)
        playlist = self._active_playlist_payloads(match_id)
        return assemble_match_package(
            playlist=playlist,
            events=[
                row
                for row in events_as_query_rows(events, match_id=match_id)
                if row.get("reviewStatus") != "rejected"
            ],
            metrics=metrics,
            corrections=corrections,
            cost={},
            secrets={},
        )

    def incident_geometry_for_match(self, match_id: str) -> dict:
        from .workbench.geometry import review_incident_geometry

        match = self.get_match(match_id)
        frames = self.load_frames(match_id)
        if not frames:
            raise FileNotFoundError(match_id)
        frame = frames[0]
        ball = frame.ball
        return review_incident_geometry(
            my_team=[{"x": float(player.x), "y": float(player.y)} for player in frame.myTeam],
            enemies=[{"x": float(player.x), "y": float(player.y)} for player in frame.enemies],
            ball=None if ball is None else {"x": float(ball.x), "y": float(ball.y)},
            attack_direction=match.config.attackDirection,
        )

    def assess_stored_match_setup(self, match_id: str) -> dict:
        from .workbench.setup import assess_match_setup

        match = self.get_match(match_id)
        config = match.config
        calibration = self.calibration_revision(match_id)
        return assess_match_setup(
            camera_profile=config.cameraProfile,
            pitch_length_m=config.pitchLengthM,
            rights=config.rights.model_dump(mode="json"),
            periods=[period.model_dump(mode="json") for period in config.periods],
            home_team=config.homeTeam,
            away_team=config.awayTeam,
            calibration_committed=bool(calibration and calibration.accepted and calibration.measured),
        )

    def four_rates_for_match(self, match_id: str) -> dict:
        self.get_match(match_id)
        try:
            payload = self.load_analysis_artifact(match_id, "four_rates")
        except FileNotFoundError:
            payload = None
        body = dict(payload or {})
        notes = [str(item) for item in body.get("notes") or []]
        if payload is None:
            notes.append("FOUR_RATES_UNRECORDED")
        if "EXPORT_FPS_IS_NOT_INFERENCE_FPS" not in notes:
            notes.append("EXPORT_FPS_IS_NOT_INFERENCE_FPS")
        return {
            "decodeCount": int(body.get("decodeCount") or 0),
            "detectorPrimaryCount": int(body.get("detectorPrimaryCount") or body.get("inferenceCount") or 0),
            "detectorRecoveryCount": int(body.get("detectorRecoveryCount") or 0),
            "trackerUpdateCount": int(body.get("trackerUpdateCount") or 0),
            "exportCount": int(body.get("exportCount") or 0),
            "exportFpsEqualsInferenceFps": False,
            "decodeFpsEqualsExportFps": False,
            "notes": notes,
        }

    @_generation_reader
    def match_metrics_for_match(self, match_id: str) -> dict:
        from .workbench.evidence import summarize_legacy_match

        with self.generation_snapshot(match_id) as generation:
            summary, _, _, _ = self.load_analytics(match_id, generation_id=generation.generationId)
            try:
                frames = self.load_frames(match_id, generation_id=generation.generationId)
            except FileNotFoundError:
                frames = []
        if summary.metricAvailability:
            return {"metrics": [item.model_dump(mode="json") for item in summary.metricAvailability]}
        controlled = sum(
            1
            for frame in frames
            if frame.possession is not None and frame.possession.team in {"my_team", "enemy"}
        )
        metrics = [
            metric.model_dump(mode="json")
            for metric in summarize_legacy_match(
                summary.model_dump(mode="json"),
                identity_continuous=self._stored_identity_continuous(match_id),
                calibration_accepted=self._stored_calibration_accepted(match_id),
                controlled_frames=controlled,
            )
        ]
        return {"metrics": metrics}

    def inspect_match_metric(self, match_id: str, metric: str) -> dict:
        from .workbench.evidence import inspect_metric

        payload = self.match_metrics_for_match(match_id)
        item = next((row for row in payload["metrics"] if row.get("metric") == metric), None)
        if item is None:
            return inspect_metric(metric)
        return inspect_metric(
            metric,
            value=item.get("value"),
            availability=str(item.get("availability") or "unknown"),
            eligible_duration=float(item.get("eligibleSeconds") or 0.0),
            exclusions=list(item.get("reasonCodes") or []),
        )

    def incident_package_for_match(self, match_id: str) -> dict:
        from .workbench.incidents import level0_incident_package

        self.get_match(match_id)
        clips = self._active_playlist_payloads(match_id)
        return level0_incident_package(clips=clips, notes=[], bookmarks=[])

    def clock_for_match(self, match_id: str) -> dict:
        self.get_match(match_id)
        try:
            source_clock = self.load_analysis_artifact(match_id, "source_clock")
        except FileNotFoundError:
            source_clock = None
        try:
            frames = self.load_frames(match_id)
        except FileNotFoundError:
            frames = []
        presentation = float(frames[0].timestamp) if frames else 0.0
        offset = 0.0
        if isinstance(source_clock, dict):
            offset = float(source_clock.get("matchClockOffsetSeconds") or 0.0)
        return {
            "presentationTimeSeconds": presentation,
            "matchClockSeconds": presentation + offset,
            "explicitMapping": bool(source_clock),
            "frameAccurateOverlay": False,
            "sourceClockRecorded": bool(source_clock),
        }

    def incident_review_for_match(self, match_id: str) -> dict:
        from .workbench.incidents import level1_positional_aid

        match = self.get_match(match_id)
        frames = self.load_frames(match_id)
        if not frames:
            raise FileNotFoundError(match_id)
        geometry = self.incident_geometry_for_match(match_id)
        start = float(frames[0].timestamp)
        end = float(frames[1].timestamp) if len(frames) > 1 else start + 0.12
        attacker = geometry.get("mostAdvancedTeammateX")
        line = geometry.get("secondLastOpponentX")
        attacker_x = None if attacker is None else float(attacker)
        line_x = None if line is None else float(line)
        samples: list[tuple[float, float]] = []
        attacking_right_to_left = match.config.attackDirection == "right_to_left"
        if attacker_x is not None and line_x is not None:
            for frame in frames[:2]:
                xs = [float(player.x) for player in frame.myTeam]
                if xs:
                    samples.append((float(frame.timestamp), min(xs) if attacking_right_to_left else max(xs)))
        return level1_positional_aid(
            touch_interval=(start, end),
            attacker_x=attacker_x,
            offside_line_x=line_x,
            uncertainty_m=3.0,
            attacker_x_by_time=tuple(samples) if samples else None,
        )

    def dpia_for_match(self, match_id: str) -> dict:
        from .workbench.privacy import dpia_screen

        match = self.get_match(match_id)
        rights = match.config.rights
        cloud_requested = match.config.llmProvider == "cloud" or rights.processingScope != "local_only"
        return dpia_screen(
            youth_footage=False,
            identifiable_faces=True,
            cloud_requested=cloud_requested,
            cloud_permitted=rights.cloudPermission,
        ).model_dump(mode="json")

    def plan_recompute(self, match_id: str, change: str):
        from .video_pipeline import IMAGE_SPACE_SAFE_CHANGES
        from .workbench.cache import REBUILD_FOR, RecomputePlan

        self.get_match(match_id)
        rebuild = list(REBUILD_FOR.get(change, []))
        return RecomputePlan(
            change=change,
            rebuild=rebuild,
            requires=["observations"] if change in IMAGE_SPACE_SAFE_CHANGES else ["sealed_worker"],
            visionRequired=change not in IMAGE_SPACE_SAFE_CHANGES,
        )

    def recompute_for_match(self, match_id: str, change: str) -> dict:
        """Compatibility entry point: recompute is now explicitly plan-only."""
        return self.plan_recompute(match_id, change).model_dump(mode="json")

    def execute_recompute(self, match_id: str, change: str):
        from .review_service import ReviewService
        from .video_pipeline import IMAGE_SPACE_SAFE_CHANGES
        from .workbench.cache import RecomputeReceipt, RecomputeRefusal

        match = self.get_match(match_id)
        self.plan_recompute(match_id, change)
        if change not in IMAGE_SPACE_SAFE_CHANGES:
            return RecomputeRefusal(reasonCodes=["VISION_REQUIRES_SEALED_WORKER"])

        observation_path = self._match_dir(match_id) / "raw_rows.json"
        if match.inputMode != "video":
            review_base = self._match_dir(match_id) / "review_base_frames.json"
            observation_path = review_base if review_base.is_file() else self.get_match_input_path(match_id)
        if not observation_path.is_file():
            return RecomputeRefusal(reasonCodes=["CACHE_MISS"])

        current = self.current_generation(match_id)
        manifest_path = self._match_dir(match_id) / "generations" / current.generationId / "manifest.json"
        artifacts = {"observations": self._sha256_file(observation_path)}
        if manifest_path.is_file():
            artifacts["generation"] = self._sha256_file(manifest_path)
        calibration = self.calibration_revision(match_id)
        if calibration is not None:
            artifacts["calibration"] = hashlib.sha256(
                json.dumps(calibration.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()

        from .semantic_commands import SemanticCommandError
        try:
            output = ReviewService(self).rebuild_generation(match_id, reason=change)
        except SemanticCommandError as exc:
            return RecomputeRefusal(reasonCodes=[exc.code])
        manifest, _ = self.generations.manifest(match_id, output.generationId)
        if manifest.observationDigest:
            artifacts["observations"] = manifest.observationDigest
        return RecomputeReceipt(
            change=change,
            inputArtifacts=artifacts,
            outputGeneration=output.generationId,
            rebuilt=["frames", "assignments", "events", "formation_timeline", "shots", "summary"],
            detectorCalls=0,
        )

    def promotion_receipt_for_match(self, match_id: str) -> dict:
        from .workbench.receipts import promotion_receipt

        sha = self.source_sha256(match_id)
        try:
            frame_count = len(self.load_frames(match_id))
        except FileNotFoundError:
            frame_count = None
        return promotion_receipt(
            source_sha256=sha,
            weights=None,
            configuration="evidence_v1",
            hardware=None,
            native_builds=[],
            selected_backend=None,
            frame_count=frame_count,
            call_count=None,
            cold_timing_ms=None,
            warm_timing_ms=None,
            peak_memory_bytes=None,
            transferred_bytes=None,
            output_quality="unproven",
            accepted_coverage=0.0,
            failure_cases=["labels_incomplete"],
            allocated_spend=0.0,
            fallback_event=None,
        )

    def assistance_fallback_for_match(self, match_id: str) -> dict:
        from .workbench.assistance import events_as_query_rows, providers_disabled_fallback

        self.get_match(match_id)
        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            events = []
        try:
            metrics = self.match_metrics_for_match(match_id)["metrics"]
        except FileNotFoundError:
            metrics = []
        return providers_disabled_fallback(
            metrics=metrics,
            events=events_as_query_rows(events, match_id=match_id),
        )

    def quality_timeline_for_match(self, match_id: str) -> dict:
        match = self.get_match(match_id)
        items: list[dict] = []
        try:
            players = self.player_observations_for_match(match_id)
        except FileNotFoundError:
            players = {"totalsWithheld": True, "reasonCodes": ["IDENTITY_DISCONTINUITY"]}
        if players.get("totalsWithheld") or "IDENTITY_DISCONTINUITY" in list(players.get("reasonCodes") or []):
            items.append({"id": "identity", "label": "identity switches", "impact": "high", "accepted": False})
        setup = self.assess_stored_match_setup(match_id)
        preview = self.preview_landmark_for_match(match_id)
        if not setup.get("certified") or preview.get("measured") is False:
            items.append({"id": "calibration", "label": "calibration drift", "impact": "high", "accepted": False})
        if match.config.myTeamCluster is None:
            items.append({"id": "team", "label": "incorrect team selection", "impact": "high", "accepted": False})
        try:
            ownership = self.classify_match_ownership(match_id)
        except FileNotFoundError:
            ownership = {"mode": "unknown"}
        if ownership.get("mode") == "unknown":
            items.append(
                {
                    "id": "possession",
                    "label": "ambiguous possession around a shot",
                    "impact": "high",
                    "accepted": False,
                }
            )
        return {"items": items, "reviewFirst": True, "accepted": False, "measured": False}

    @_generation_reader
    def heatmap_for_match(self, match_id: str) -> dict:
        from .workbench.quantities import heatmap_availability

        self.get_match(match_id)
        identity = self._stored_identity_continuous(match_id)
        geometry = self._stored_calibration_accepted(match_id)
        result = heatmap_availability(identity_continuous=identity and geometry)
        calibration = self.calibration_revision(match_id)
        dimensions = ({"pitchLengthM": calibration.pitchLengthM, "pitchWidthM": calibration.pitchWidthM}
                      if geometry and calibration is not None else None)
        return {**result, "identityContinuous": identity, "geometryEligible": geometry,
                "pitchDimensions": dimensions,
                "reasonCodes": ([] if identity else ["IDENTITY_DISCONTINUITY"]) +
                               ([] if geometry else ["CALIBRATION_UNAVAILABLE"])}

    @_generation_reader
    def identity_for_match(self, match_id: str) -> dict:
        from .workbench.identity import (
            appearance_embedding_policy,
            candidate_rejoin,
            cross_season_identity,
            face_recognition,
            reconnect_across_cut,
        )
        from .workbench.media import detect_camera_cuts

        self.get_match(match_id)
        try:
            frames = self.load_frames(match_id)
        except FileNotFoundError:
            frames = []
        times = [float(frame.timestamp) for frame in frames]
        cuts = detect_camera_cuts(times) if len(times) > 1 else []
        payload = reconnect_across_cut(cut_detected=bool(cuts))
        payload["appearance"] = appearance_embedding_policy()
        payload["faceRecognition"] = face_recognition(requested=False)
        payload["crossSeasonIdentity"] = cross_season_identity(requested=False)
        payload["candidateRejoin"] = candidate_rejoin()
        payload["cutCount"] = len(cuts)
        payload["identityContinuous"] = self._stored_identity_continuous(match_id)
        return payload

    @_generation_reader
    def formation_for_match(self, match_id: str) -> dict:
        from .workbench.quantities import formation_availability

        match = self.get_match(match_id)
        try:
            _, _, timeline, _ = self.load_analytics(match_id)
        except FileNotFoundError:
            timeline = []
        role_context = match.config.myTeamCluster is not None
        return formation_availability(eligible_windows=len(timeline), role_context=role_context)

    def partition_events_for_match(self, match_id: str) -> dict:
        from .workbench.assistance import events_as_query_rows
        from .workbench.events import partition_events

        self.get_match(match_id)
        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            events = []
        return partition_events(events_as_query_rows(events, match_id=match_id))

    def provenance_for_match(self, match_id: str, claimed_evidence_ids: list[str] | None = None) -> dict:
        from .workbench.assistance import events_as_query_rows
        from .workbench.evidence import records_from_match
        from .workbench.reports import claim_provenance

        self.get_match(match_id)
        try:
            frames = self.load_frames(match_id)
        except FileNotFoundError:
            frames = []
        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            events = []
        known = {record.evidenceId for record in records_from_match(frames, events)}
        if claimed_evidence_ids is None:
            claims = [
                {"evidenceIds": list(row.get("evidenceIds") or [])}
                for row in events_as_query_rows(events, match_id=match_id)
            ]
        else:
            claims = [{"evidenceIds": list(claimed_evidence_ids)}]
        return claim_provenance(claims=claims, known_evidence_ids=known)

    def coverage_for_match(self, match_id: str) -> dict:
        from .workbench.assistance import events_as_query_rows
        from .workbench.reports import coverage_aware_selector

        self.get_match(match_id)
        try:
            frames = self.load_frames(match_id)
        except FileNotFoundError:
            frames = []
        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            events = []
        frame_rows = [{"frameId": frame.frameId, "timestamp": frame.timestamp} for frame in frames]
        return coverage_aware_selector(
            frames=frame_rows,
            events=events_as_query_rows(events, match_id=match_id),
            max_frames=3,
        )

    def shot_quality_for_match(self, match_id: str) -> dict:
        from .workbench.shot_model import experimental_shot_quality, extract_shot_features

        self.get_match(match_id)
        try:
            _, _, _, shots = self.load_analytics(match_id)
        except FileNotFoundError:
            shots = []
        items = []
        for shot in shots:
            features = extract_shot_features({"x": float(shot.x), "y": float(shot.y), "inBox": bool(shot.inBox)})
            items.append(experimental_shot_quality(features).model_dump(mode="json"))
        return {
            "publishedLabel": "experimental_shot_quality",
            "calibratedXg": False,
            "items": items,
        }

    def proxy_assets_for_match(self, match_id: str) -> dict:
        from .workbench.media import derive_proxy_assets, run_proxy_ffmpeg_job

        original = self.get_match_input_path(match_id)
        sha = self.source_sha256(match_id)
        try:
            frames = self.load_frames(match_id)
            pts = [int(float(frame.timestamp) * 90000) for frame in frames[:8]] or [0]
        except FileNotFoundError:
            pts = [0]
        destination = self._match_dir(match_id) / "proxy.mp4"
        try:
            receipt = dict(
                run_proxy_ffmpeg_job(
                    original,
                    destination,
                    original_sha256=sha,
                    hash_cache=self.hash_cache,
                )
            )
            receipt["ranFfmpeg"] = True
            return receipt
        except Exception as error:
            from .workbench.media_execution import media_failure_receipt
            receipt = dict(
                derive_proxy_assets(
                    original,
                    original_sha256=sha,
                    original_pts=pts,
                    time_base=(1, 90000),
                    hash_cache=self.hash_cache,
                )
            )
            receipt["ranFfmpeg"] = False  # Legacy field: no completed FFmpeg proxy.
            receipt["mediaExecution"] = media_failure_receipt(error)
            receipt["mediaExecution"]["fallback"] = "not_attempted"
            receipt["reasonCodes"] = [receipt["mediaExecution"]["outcome"]]
            receipt["assetsAvailability"] = "planned_only"
            receipt["frameExactExport"]["validatedDecodeReencode"] = False
            return receipt

    @_generation_reader
    def edit_list_for_match(self, match_id: str, *, generation_id: str | None = None) -> dict:
        from .workbench.media import store_edit_list
        ref = self.current_generation(match_id)
        sha = self.source_sha256(match_id)
        intervals = []
        for payload in self._active_playlist_payloads(match_id):
            start = payload.get("timestampStart", payload.get("start"))
            end = payload.get("timestampEnd", payload.get("end"))
            if start is not None and end is not None:
                intervals.append({"start": float(start), "end": float(end)})
        return {**store_edit_list(source_sha256=sha, intervals=intervals),
                "matchId": match_id, "generationId": ref.generationId,
                "provenance": "generation_bound_analyst_selection"}

    @_generation_reader
    def render_edit_for_match(self, match_id: str, *, start: float, end: float,
                              generation_id: str | None = None) -> dict:
        from .workbench.media import render_on_demand
        edits = self.edit_list_for_match(match_id, generation_id=generation_id)
        return {**render_on_demand(edits, start=start, end=end),
                "matchId": match_id, "generationId": edits["generationId"],
                "executionStatus": "not_run"}

    def write_alongside_for_match(self, match_id: str) -> dict:
        from .workbench.artifacts import ArtifactStore, write_alongside

        self.get_match(match_id)
        store = ArtifactStore(self.storage_root / "artifacts")
        namespace = f"match:{match_id}"
        previous = store.put(b"report-v1", namespace=namespace)
        return write_alongside(store, previous_digest=previous, payload=b"report-v2", namespace=namespace)

    def tracklets_for_match(self, match_id: str) -> dict:
        from .workbench.identity import assign_tracklet, tracker_chunk
        from .workbench.media import detect_camera_cuts

        self.get_match(match_id)
        try:
            frames = self.load_frames(match_id)
            times = [float(frame.timestamp) for frame in frames]
            cuts = detect_camera_cuts(times) if len(times) > 1 else []
        except FileNotFoundError:
            cuts = []
        return {
            "assignment": assign_tracklet(roster_id=None, reviewed=False),
            "chunk": tracker_chunk(scene_discontinuity=bool(cuts), broadcast_replay=False),
            "silentlyReconnected": False,
        }

    @_generation_reader
    def derived_distance_for_match(self, match_id: str) -> dict:
        from .workbench.geometry import derived_distance
        from .workbench.media import detect_camera_cuts

        self.get_match(match_id)
        try:
            frames = self.load_frames(match_id)
            times = [float(frame.timestamp) for frame in frames]
            cuts = detect_camera_cuts(times) if len(times) > 1 else []
        except FileNotFoundError:
            frames = []
            cuts = []
        identity_gap = not self._stored_identity_continuous(match_id)
        calibration_missing = not self._stored_calibration_accepted(match_id)
        evaluation = self._load_calibration_evaluation(match_id)
        residual = evaluation.get("p95M")
        uncertainty_m = float(residual) if residual is not None else 0.0
        delta_m = 0.0
        revision = self.calibration_revision(match_id)
        if frames and not identity_gap and not calibration_missing and not cuts:
            from .workbench.geometry import normalized_path_distance_m
            delta_m = normalized_path_distance_m(frames, pitch_length_m=revision.pitchLengthM,
                                                pitch_width_m=revision.pitchWidthM)
        return derived_distance(
            delta_m=delta_m,
            uncertainty_m=uncertainty_m,
            cut_bridged=bool(cuts),
            identity_gap=identity_gap,
            calibration_missing=calibration_missing,
        )

    def shot_features_for_match(self, match_id: str) -> dict:
        from .workbench.shot_model import missing_shot_features

        self.get_match(match_id)
        try:
            _, _, _, shots = self.load_analytics(match_id)
        except FileNotFoundError:
            shots = []
        if not shots:
            record = missing_shot_features({})
            return {"recorded": True, "missing": list(record["missing"]), "imputedAsCalibrated": False}
        missing: list[str] = []
        for shot in shots:
            record = missing_shot_features({"x": shot.x, "y": shot.y, "inBox": shot.inBox})
            missing.extend(record["missing"])
        return {"recorded": True, "missing": sorted(set(missing)), "imputedAsCalibrated": False}

    def corrupted_import_for_match(self, match_id: str, actual_sha256: str) -> dict:
        from .workbench.recovery import corrupted_import

        expected = self.source_sha256(match_id)
        return corrupted_import(expected_sha256=expected, actual_sha256=actual_sha256)

    def restore_exercise_run(self) -> dict:
        from .workbench.recovery import restore_exercise

        return restore_exercise(self.storage_root / "restore-source", self.storage_root / "restore-dest")

    def history_for_match(self, match_id: str) -> dict:
        from .workbench.review import change_history

        self.get_match(match_id)
        return change_history(self.list_corrections(match_id))

    def cache_identity_for_match(self, match_id: str) -> dict:
        self.get_match(match_id)
        layers = {}
        for layer in ("detection", "tracking"):
            try:
                layers[layer] = self.load_analysis_artifact(match_id, f"{layer}_identity")
            except FileNotFoundError:
                layers[layer] = {"digest": None, "reusable": False}
        return {
            "namespace": "production",
            "identity": layers["tracking"]["digest"],
            "reusable": layers["tracking"]["reusable"],
            "layers": layers,
            "compatibleWithDevelopment": False,
        }

    def migrate_legacy_for_match(self, match_id: str) -> dict:
        from .workbench.evidence import migrate_legacy_record, rollback_reader

        summary, *_ = self.load_analytics(match_id)
        migrated = migrate_legacy_record(
            {
                "possession": summary.possession,
                "myTeamDistance": None,
                "enemyDistance": None,
                "controlledFrames": 0,
            }
        )
        return {"migrated": migrated, "rollback": rollback_reader(migrated), "rewrotePastOutcomes": False}

    def attack_direction_for_match(self, match_id: str, *, team: str, period: int) -> dict:
        from .workbench.quantities import attack_direction_for

        match = self.get_match(match_id)
        mapping = {("my_team", 1): match.config.attackDirection}
        return {
            "direction": attack_direction_for(team=team, period=period, mapping=mapping),
            "fromStoredConfig": True,
            "team": team,
            "period": period,
        }

    def interrupted_upload_run(self) -> dict:
        from .workbench.recovery import interrupted_upload

        return interrupted_upload(self.storage_root / "uploads" / "interrupted.bin")

    def load_raw_rows(self, match_id: str) -> list[dict]:
        payload = self._read_json(self._match_dir(match_id) / "raw_rows.json")
        return [dict(item) for item in payload]

    @_generation_reader
    def load_analytics(
        self,
        match_id: str,
        *,
        generation_id: str | None = None,
    ) -> tuple[MatchSummary, list[BallOwnership], list[FormationSegment], list[ShotAnalytics]]:
        payload = self.generations.payload(match_id, "analytics.json", generation_id)
        summary = self._video_ball_signal_summary(match_id, MatchSummary.model_validate(payload["summary"]))
        assignments = [BallOwnership.model_validate(item) for item in payload["ballAssignments"]]
        if not any(assignment.team in {"my_team", "enemy"} for assignment in assignments):
            summary = summary.model_copy(update={"possession": None})
        formation_timeline = [FormationSegment.model_validate(item) for item in payload.get("formationTimeline", [])]
        shots = [ShotAnalytics.model_validate(item) for item in payload.get("shots", [])]
        summary = self._physical_summary_view(match_id, summary, generation_id=generation_id)
        return summary, assignments, formation_timeline, shots

    def load_events(self, match_id: str, *, generation_id: str | None = None) -> list[DetectedEvent]:
        payload = self.generations.payload(match_id, "events.json", generation_id)
        return [DetectedEvent.model_validate(item) for item in payload]

    def load_accepted_match_state(self, match_id: str, *, generation_id: str | None = None) -> dict:
        with self.generation_snapshot(match_id, generation_id=generation_id) as ref:
            manifest, _ = self.generations.manifest(match_id, ref.generationId)
            if "accepted_match_state.json" in manifest.files:
                return self.generations.payload(match_id, "accepted_match_state.json", ref.generationId)
            from .accepted_state import bind_state
            return bind_state(match_id, ref.generationId, None)

    def load_analysis_artifact(self, match_id: str, analysis_type: str) -> dict:
        if analysis_type == "accepted_match_state" and any((self.generations.root(match_id) / name).exists()
                for name in ("current_generation.json", ".generation-format.json", "generations")):
            return self.load_accepted_match_state(match_id)
        payload = self._read_json(self._match_dir(match_id) / f"{analysis_type}.json")
        return dict(payload)

    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        with Storage._atomic_text_destination(path) as handle:
            json.dump(payload, handle, indent=2)

    @staticmethod
    def _write_json_array(path: Path, values: Iterable[object]) -> None:
        encoder = json.JSONEncoder(separators=(",", ":"))
        with Storage._atomic_text_destination(path) as handle:
            handle.write("[")
            for index, value in enumerate(values):
                if index:
                    handle.write(",")
                for chunk in encoder.iterencode(value):
                    handle.write(chunk)
            handle.write("]")

    @staticmethod
    @contextmanager
    def _atomic_text_destination(path: Path) -> Iterator[TextIO]:
        """Publish text durably, restoring the prior path on commit failure."""
        temporary_fd, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        backup: Path | None = None
        directory_fd = -1
        published = False
        rollback_uncertain = False
        try:
            handle = os.fdopen(temporary_fd, "w", encoding="utf-8")
            temporary_fd = -1
            with handle:
                yield handle
                handle.flush()
                os.fsync(handle.fileno())

            directory_fd = os.open(
                path.parent,
                os.O_RDONLY
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                prior = os.stat(path, follow_symlinks=False)
            except FileNotFoundError:
                prior = None
            if prior is not None:
                if not stat.S_ISREG(prior.st_mode):
                    raise OSError("atomic JSON destination is not a regular file")
                backup = path.with_name(f".{path.name}.{uuid.uuid4().hex}.bak")
                os.link(path, backup, follow_symlinks=False)
                retained = os.stat(backup, follow_symlinks=False)
                if (retained.st_dev, retained.st_ino) != (prior.st_dev, prior.st_ino):
                    raise OSError("atomic JSON destination changed before backup")
                os.fsync(directory_fd)

            os.replace(temporary, path)
            published = True
            os.fsync(directory_fd)
            if backup is not None:
                try:
                    backup.unlink()
                    backup = None
                except OSError:
                    pass  # The durable new path is authoritative; cleanup may retry below.
        except BaseException as error:
            if published:
                try:
                    if backup is None:
                        path.unlink()
                    else:
                        os.replace(backup, path)
                        backup = None
                    os.fsync(directory_fd)
                except BaseException:
                    rollback_uncertain = True
                    raise StorageWriteOutcomeUncertain(
                        "atomic JSON write outcome is uncertain; inspect before retrying"
                    ) from error
            raise
        finally:
            if temporary_fd >= 0:
                os.close(temporary_fd)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            if backup is not None and not rollback_uncertain:
                try:
                    backup.unlink(missing_ok=True)
                except OSError:
                    pass
            if directory_fd >= 0:
                try:
                    os.close(directory_fd)
                except OSError:
                    pass

    @staticmethod
    def _read_json(path: Path) -> object:
        return json.loads(path.read_text(encoding="utf-8"))

    # ===== Review Bundles / Playlists =====

    def _bundle_dir(self) -> Path:
        return self._review_storage.bundle_dir()

    def list_review_bundles(self, tags: list[str] | None = None) -> list[ReviewBundle]:
        return self._review_storage.list_review_bundles(tags)

    def get_review_bundle(self, bundle_id: str) -> ReviewBundle:
        return self._review_storage.get_review_bundle(bundle_id)

    @contextmanager
    def _bound_bundle_items(self, items):
        with self._review_storage.bound_bundle_items(items) as bound_items:
            yield bound_items

    def create_review_bundle(
        self,
        name: str,
        description: str = "",
        items: list | None = None,
        tags: list[str] | None = None,
    ) -> ReviewBundle:
        return self._review_storage.create_review_bundle(
            name,
            description=description,
            items=items,
            tags=tags,
        )

    def update_review_bundle(
        self,
        bundle_id: str,
        name: str | None = None,
        description: str | None = None,
        items: list | None = None,
        tags: list[str] | None = None,
    ) -> ReviewBundle:
        return self._review_storage.update_review_bundle(
            bundle_id,
            name=name,
            description=description,
            items=items,
            tags=tags,
        )

    def delete_review_bundle(self, bundle_id: str) -> None:
        self._review_storage.delete_review_bundle(bundle_id)

    # ===== Annotations =====

    def _annotations_path(self, match_id: str) -> Path:
        return self._review_storage.annotations_path(match_id)

    def list_annotations(self, match_id: str) -> list[TacticalAnnotationRecord]:
        return self._review_storage.list_annotations(match_id)

    def create_annotation(
        self,
        match_id: str,
        payload: CreateAnnotationRequest,
    ) -> TacticalAnnotationRecord:
        return self._review_storage.create_annotation(match_id, payload)

    def delete_annotation(self, match_id: str, annotation_id: str) -> None:
        self._review_storage.delete_annotation(match_id, annotation_id)

    # ===== Match Issues =====

    def _issues_path(self, match_id: str) -> Path:
        return self._review_storage.issues_path(match_id)

    def list_issues(self, match_id: str) -> list[MatchIssueRecord]:
        return self._review_storage.list_issues(match_id)

    def create_issue(
        self,
        match_id: str,
        payload: CreateIssueRequest,
    ) -> MatchIssueRecord:
        return self._review_storage.create_issue(match_id, payload)

    def delete_issue(self, match_id: str, issue_id: str) -> None:
        self._review_storage.delete_issue(match_id, issue_id)

    # ===== Semantic Search Support =====

    def _physical_summary_view(self, match_id: str, summary: MatchSummary, *, generation_id: str | None = None) -> MatchSummary:
        """Read-only compatibility for pre-C02 snapshots with unscoped physical totals.

        The stored values remain historical bytes, not newly approved measurements.
        This same filter is used by compact dashboards and full analytics readers.
        """
        from .identity_eligibility import identity_eligibility

        try:
            with self.generation_snapshot(match_id, generation_id=generation_id) as ref:
                manifest, _ = self.generations.manifest(match_id, ref.generationId)
                context = manifest.identityContext
        except FileNotFoundError:
            if generation_id is not None:
                raise
            context = None  # Explicit pre-generation migration, never proof of approval.
        eligibility = identity_eligibility(context)
        geometry = isinstance(context, dict) and context.get("geometryEligible") is True
        if eligibility["continuous"] and geometry:
            return summary
        reasons = list(eligibility["reasonCodes"])
        if not geometry:
            reasons += ["CALIBRATION_OR_MOVEMENT_UNAVAILABLE"]
        physical_names = {"my_team_distance_m", "enemy_distance_m", "my_team_top_speed_kmh",
                          "enemy_top_speed_kmh", "my_team_sprints", "enemy_sprints"}
        availability = [item.model_copy(update={
            "availability": "withheld", "value": None,
            "reasonCodes": list(dict.fromkeys([*item.reasonCodes, *reasons])),
        }) if item.metric in physical_names else item for item in summary.metricAvailability]
        # Old summaries may contain no availability entries at all. Publish an
        # explicit withheld disposition on the read view, without editing history.
        from .schemas import MetricAvailabilityRecord
        present = {item.metric for item in availability}
        availability.extend(MetricAvailabilityRecord(
            metric=metric, value=None, availability="withheld", reasonCodes=reasons,
        ) for metric in sorted(physical_names - present))
        return summary.model_copy(update={
            **{name: None for name in ("myTeamDistance", "enemyDistance", "myTeamTopSpeed",
                                      "enemyTopSpeed", "myTeamSprints", "enemySprints")},
            "metricAvailability": availability,
        })

    @_generation_reader
    def _indexed_match_summary(self, match_id: str, encoded: str | None, *, input_mode: str | None = None) -> MatchSummary:
        # SQLite is a rebuildable index, never a competing analytical authority.
        try:
            # A dashboard needs the small bound summary, never full trajectories
            # or an unversioned/stale SQL subtotal. The read does not backfill SQL.
            payload = self.generations.payload(match_id, "summary.json")
            summary = self._video_ball_signal_summary(match_id, MatchSummary.model_validate(payload), input_mode=input_mode)
            return self._physical_summary_view(match_id, summary)
        except FileNotFoundError:
            return self.load_analytics(match_id)[0]  # Unversioned legacy read only.

    def list_matches_with_analytics(self) -> list[dict]:
        """List all matches that have analytics available.
        
        Returns list of dicts with matchId, matchName, summary for each match.
        """
        with self._connect() as connection:
            matches = connection.execute(
                """
                SELECT id, name, input_mode, created_at, analytics_summary_json
                FROM matches
                WHERE status IN ('completed', 'ready')
                ORDER BY created_at DESC
                """
            ).fetchall()
        results = []

        for match in matches:
            try:
                summary = self._indexed_match_summary(match["id"], match["analytics_summary_json"], input_mode=match["input_mode"])
                results.append({
                    "matchId": match["id"],
                    "matchName": match["name"],
                    "summary": summary.model_dump(mode="json"),
                    "createdAt": match["created_at"],
                })
            except FileNotFoundError:
                continue

        return results

    def get_match_summary_for_search(self, match_id: str) -> dict | None:
        """Get match summary data for search indexing.
        
        Returns dict with summary data or None if not available.
        """
        with self._connect() as connection:
            match = connection.execute(
                "SELECT id, name, input_mode, analytics_summary_json FROM matches WHERE id = ?",
                (match_id,),
            ).fetchone()
        if match is None:
            return None
        try:
            summary = self._indexed_match_summary(match_id, match["analytics_summary_json"], input_mode=match["input_mode"])
            return {
                "matchId": match_id,
                "matchName": match["name"],
                "summary": summary.model_dump(mode="json"),
            }
        except FileNotFoundError:
            return None
