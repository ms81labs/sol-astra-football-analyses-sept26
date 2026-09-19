"""C01: immutable generations, pointer authority and explicit maintenance.

Lock order is review -> lifetime -> publication. Readers release publication
before loading payloads; only explicit retention takes lifetime exclusively.
Local POSIX filesystems are supported; no thread-only lock fallback is used.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import threading
import uuid

from .schemas import MatchConfig, MatchSummary, FrameData, DetectedEvent, BallOwnership, FormationSegment, ShotAnalytics
from .workbench.contracts import CalibrationRevision
from .workbench.contracts import GenerationManifest, GenerationRef
from .workbench.errors import DomainError


class GenerationRecoveryRequired(DomainError):
    """Authoritative data is unavailable; a GET must not repair or guess it."""
    code = "GENERATION_RECOVERY_REQUIRED"


class StaleGeneration(DomainError):
    code = "STALE_GENERATION"


class RetentionBusy(DomainError):
    code = "GENERATION_RETENTION_BUSY"


class GenerationCommitUncertain(GenerationRecoveryRequired):
    """Pointer replacement occurred but its durability could not be confirmed."""


_UNSET = object()
_REQUIRED = {"frames.json", "events.json", "analytics.json", "shots.json", "summary.json"}
_ANALYTICAL = {
    "attackDirection", "manualHomographyPoints", "myTeamCluster", "autoHomography",
    "cameraProfile", "pitchLengthM", "pitchWidthM", "periods", "calibrationCommitted",
}
_ID = re.compile(r"[A-Za-z0-9_-]{1,160}\Z")


def _identifier(value: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise GenerationRecoveryRequired("Invalid generation or match identifier")
    return value


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def semantic_config(config: MatchConfig | dict) -> dict:
    data = config.model_dump(mode="json") if isinstance(config, MatchConfig) else config
    return {key: data[key] for key in sorted(_ANALYTICAL) if key in data}


def _stat(path: Path) -> list[int]:
    result = path.lstat()
    if not stat.S_ISREG(result.st_mode):
        raise GenerationRecoveryRequired("Generation member is not a regular file")
    return [result.st_dev, result.st_ino, result.st_size, result.st_mtime_ns, result.st_ctime_ns]


def _sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class GenerationStore:
    """Storage's generation coordinator; no second database or commit authority."""

    def __init__(self, storage):
        self.storage = storage
        self.local = threading.local()

    def root(self, match_id: str) -> Path:
        root = self.storage.storage_root / "matches" / _identifier(match_id)
        if root.is_symlink():
            raise GenerationRecoveryRequired("Symlink match directory is not supported")
        return root

    def prepare(self, match_id: str) -> None:
        """Admission/migration only. Routine readers never create lock files."""
        root = self.root(match_id)
        root.mkdir(parents=True, exist_ok=True)
        for name in (".review.lock", ".generation.lifetime.lock", ".generation.lock"):
            fd = os.open(root / name, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
            os.close(fd)

    @contextmanager
    def guard(self, match_id: str, kind: str, *, exclusive=False, blocking=True):
        try:
            import fcntl
        except ImportError as exc:
            raise GenerationRecoveryRequired("Cross-process POSIX locks are required") from exc
        locks = getattr(self.local, "locks", None)
        if locks is None:
            locks = self.local.locks = {}
        key = (match_id, kind)
        retained = locks.get(key)
        if retained:
            if exclusive and not retained[1]:
                raise RetentionBusy("A shared lifetime pin cannot be upgraded")
            yield
            return
        filename = {"review": ".review.lock", "lifetime": ".generation.lifetime.lock", "publication": ".generation.lock"}[kind]
        try:
            fd = os.open(self.root(match_id) / filename, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        except OSError as exc:
            raise GenerationRecoveryRequired("Generation controls require explicit initialisation") from exc
        try:
            operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            if not blocking:
                operation |= fcntl.LOCK_NB
            try:
                fcntl.flock(fd, operation)
            except BlockingIOError as exc:
                raise RetentionBusy("An active reader or publisher defers retention") from exc
            locks[key] = (fd, exclusive)
            try:
                yield
            finally:
                locks.pop(key, None)
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def _read(self, path):
        try:
            return self.storage._read_json(path)
        except (OSError, ValueError, TypeError) as exc:
            raise GenerationRecoveryRequired(f"Unreadable generation metadata: {path.name}") from exc

    def _pointer(self, match_id):
        root = self.root(match_id)
        path = root / "current_generation.json"
        if not path.exists():
            generations = root / "generations"
            if generations.exists() and any(generations.iterdir()):
                raise GenerationRecoveryRequired("Missing authoritative pointer; candidates are not commits")
            if (root / ".generation-format.json").exists():
                raise GenerationRecoveryRequired("Missing pointer in an initialised generation store")
            raise FileNotFoundError(f"No published generation for {match_id}")
        try:
            _stat(path)
        except OSError as exc:
            raise GenerationRecoveryRequired("Unreadable generation pointer") from exc
        pointer = self._read(path)
        if not isinstance(pointer, dict) or not isinstance(pointer.get("generationId"), str):
            raise GenerationRecoveryRequired("Malformed generation pointer")
        _identifier(pointer["generationId"])
        return pointer

    def manifest(self, match_id, generation_id):
        root = self.root(match_id) / "generations"
        directory = root / _identifier(generation_id)
        if root.is_symlink() or directory.is_symlink():
            raise GenerationRecoveryRequired("Symlink generation directory is not supported")
        try:
            manifest = GenerationManifest.model_validate(self._read(directory / "manifest.json"))
        except (ValueError, TypeError) as exc:
            raise GenerationRecoveryRequired("Invalid generation manifest") from exc
        if manifest.matchId != match_id or manifest.generationId != generation_id:
            raise GenerationRecoveryRequired("Manifest match/generation identity mismatch")
        if manifest.schemaVersion not in (1, 2) or not _REQUIRED <= manifest.files.keys():
            raise GenerationRecoveryRequired("Unsupported or incomplete generation manifest")
        for name in manifest.files:
            if Path(name).name != name or name in (".", "..") or not name.endswith(".json"):
                raise GenerationRecoveryRequired("Invalid generation artifact path")
        return manifest, directory

    def _seal(self, match_id, generation_id):
        return self.root(match_id) / ".generation-verified" / f"{_identifier(generation_id)}.json"

    def verify(self, match_id, generation_id, *, expected_digest=None):
        """Full hashing at admission/publication/recovery, never on a GET."""
        manifest, directory = self.manifest(match_id, generation_id)
        manifest_before = _stat(directory / "manifest.json")
        manifest_hash = self.storage._sha256_file(directory / "manifest.json")
        if expected_digest is not None and expected_digest != manifest_hash:
            raise GenerationRecoveryRequired("Pointer/manifest digest mismatch")
        metadata = {}
        for name, digest in manifest.files.items():
            path = directory / name
            try:
                before = _stat(path)
            except OSError as exc:
                raise GenerationRecoveryRequired(f"Missing required artifact: {name}") from exc
            declared = manifest.fileMetadata.get(name)
            if manifest.schemaVersion == 2 and (
                not isinstance(declared, dict) or declared.get("byteSize") != before[2]
                or declared.get("schema") != name + ":1"
            ):
                raise GenerationRecoveryRequired(f"Invalid artifact size/schema declaration: {name}")
            if self.storage._sha256_file(path) != digest or _stat(path) != before:
                raise GenerationRecoveryRequired(f"Artifact integrity failure: {name}")
            metadata[name] = before
        # Validate the actual published schemas and duplicated summary/shot views.
        frames = self._read(directory / "frames.json")
        events = self._read(directory / "events.json")
        analytics = self._read(directory / "analytics.json")
        try:
            if not isinstance(frames, list) or not isinstance(events, list):
                raise ValueError("Frames and events must be arrays")
            if not isinstance(analytics, dict) or any(
                not isinstance(analytics.get(name, []), list)
                for name in ("ballAssignments", "formationTimeline", "shots")
            ):
                raise ValueError("Invalid analytics collection")
            for item in frames:
                FrameData.model_validate(item)
            for item in events:
                DetectedEvent.model_validate(item)
            MatchSummary.model_validate(analytics["summary"])
            for item in analytics["ballAssignments"]:
                BallOwnership.model_validate(item)
            for item in analytics.get("formationTimeline", []):
                FormationSegment.model_validate(item)
            for item in analytics.get("shots", []):
                ShotAnalytics.model_validate(item)
            if analytics["summary"] != self._read(directory / "summary.json"):
                raise ValueError("Summary views disagree")
            if analytics.get("shots", []) != self._read(directory / "shots.json"):
                raise ValueError("Shot views disagree")
            if manifest.calibrationData is not None:
                calibration = CalibrationRevision.model_validate(manifest.calibrationData)
                if calibration.revisionId != manifest.calibrationRevision:
                    raise ValueError("Calibration revision binding mismatch")
            if manifest.effectiveConfig is not None:
                if manifest.schemaVersion == 2 and "config.json" not in manifest.files:
                    raise ValueError("Missing configuration artifact")
                if set(manifest.effectiveConfig) - _ANALYTICAL:
                    raise ValueError("Operational policy cannot be snapshot configuration")
                MatchConfig.model_validate(manifest.effectiveConfig)
                if manifest.semanticConfigRevision != _digest(manifest.effectiveConfig):
                    raise ValueError("Configuration revision mismatch")
                if "config.json" in manifest.files and self._read(directory / "config.json") != manifest.effectiveConfig:
                    raise ValueError("Configuration artifact mismatch")
        except (ValueError, TypeError, KeyError) as exc:
            raise GenerationRecoveryRequired("Generation schema validation failed") from exc
        metadata["manifest.json"] = _stat(directory / "manifest.json")
        if metadata["manifest.json"] != manifest_before:
            raise GenerationRecoveryRequired("Manifest changed during verification")
        seal = {"manifestSha256": manifest_hash, "files": metadata}
        seal_path = self._seal(match_id, generation_id)
        seal_path.parent.mkdir(exist_ok=True)
        if not seal_path.exists() or self._read(seal_path) != seal:
            self.storage._write_json(seal_path, seal)
        return manifest, manifest_hash

    def resolve(self, match_id, generation_id=None):
        pointer = self._pointer(match_id) if generation_id is None else None
        gid = pointer["generationId"] if pointer else generation_id
        manifest, directory = self.manifest(match_id, gid)
        seal = self._read(self._seal(match_id, gid))
        expected = pointer.get("manifestSha256") if pointer else None
        if not isinstance(seal, dict) or not isinstance(seal.get("files"), dict):
            raise GenerationRecoveryRequired("Missing verification receipt")
        if pointer is not None and expected != seal.get("manifestSha256"):
            raise GenerationRecoveryRequired("Pointer binding requires explicit verification")
        if set(seal["files"]) != set(manifest.files) | {"manifest.json"}:
            raise GenerationRecoveryRequired("Incomplete verification receipt")
        for name, metadata in seal["files"].items():
            try:
                if _stat(directory / name) != metadata:
                    raise GenerationRecoveryRequired("Immutable artifact changed; verification required")
            except OSError as exc:
                raise GenerationRecoveryRequired("Required generation artifact is missing") from exc
        return GenerationRef(
            matchId=match_id, generationId=gid, manifestSha256=seal["manifestSha256"],
            publishedAt=manifest.publishedAt, correctionHead=manifest.correctionHead,
            calibrationRevision=manifest.calibrationRevision,
            semanticConfigRevision=manifest.semanticConfigRevision,
            migrated=bool(manifest.algorithmVersions.get("legacy_import")),
        )

    def pinned(self, match_id):
        return getattr(self.local, "pins", {}).get(match_id)

    @contextmanager
    def snapshot(self, match_id, generation_id=None):
        pins = getattr(self.local, "pins", None)
        if pins is None:
            pins = self.local.pins = {}
        previous = pins.get(match_id)
        if previous is not None and (generation_id is None or previous.generationId == generation_id):
            yield previous
            return
        with self.guard(match_id, "lifetime"):
            with self.guard(match_id, "publication"):
                ref = self.resolve(match_id, generation_id)
            pins[match_id] = ref
            try:
                yield ref
            finally:
                if previous is None:
                    pins.pop(match_id, None)
                else:
                    pins[match_id] = previous

    def payload(self, match_id, filename, generation_id=None):
        if filename not in _REQUIRED | {"config.json"}:
            raise GenerationRecoveryRequired("Unsupported generation payload")
        try:
            with self.snapshot(match_id, generation_id) as ref:
                directory = self.root(match_id) / "generations" / ref.generationId
                seal = self._read(self._seal(match_id, ref.generationId))
                expected = seal["files"].get(filename)
                try:
                    if expected is None or _stat(directory / filename) != expected:
                        raise GenerationRecoveryRequired("Immutable payload changed; verification required")
                    result = self._read(directory / filename)
                    if _stat(directory / filename) != expected:
                        raise GenerationRecoveryRequired("Payload changed during read")
                except OSError as exc:
                    raise GenerationRecoveryRequired("Required payload unavailable") from exc
                # The first C01 migration copied legacy summary defaults verbatim.
                # Preserve those immutable bytes, but retain load_analytics' existing
                # unknown-possession rule on historical summary reads as well.
                if filename == "summary.json" and ref.migrated:
                    manifest, _ = self.manifest(match_id, ref.generationId)
                    if manifest.algorithmVersions.get("legacy_import") != "3":
                        return self.storage.load_analytics(
                            match_id, generation_id=ref.generationId
                        )[0].model_dump(mode="json")
                return result
        except FileNotFoundError:
            # Pre-generation compatibility/artifact-only records remain readable,
            # but are not imported, indexed, or represented as committed snapshots.
            if generation_id is not None:
                raise
            return self.storage._read_json(self.root(match_id) / filename)

    def configuration(self, match_id, live_config):
        deferred = getattr(self.local, "deferred", {}).get(match_id)
        if deferred and deferred.get("publication"):
            effective = deferred["publication"][0].effectiveConfig
            return MatchConfig.model_validate({**live_config.model_dump(mode="json"), **(effective or {})})
        candidate = getattr(self.local, "candidates", {}).get(match_id)
        if candidate is not None:
            return candidate[0]
        root = self.root(match_id)
        if not (root / "current_generation.json").exists() and not (root / "generations").exists() and not (root / ".generation-format.json").exists():
            return live_config
        try:
            with self.snapshot(match_id) as ref:
                manifest, _ = self.manifest(match_id, ref.generationId)
                if manifest.effectiveConfig is None:
                    return live_config
                return MatchConfig.model_validate({**live_config.model_dump(mode="json"), **manifest.effectiveConfig})
        except FileNotFoundError:
            return live_config

    @contextmanager
    def candidate(self, match_id, config, calibration):
        candidates = getattr(self.local, "candidates", None)
        if candidates is None:
            candidates = self.local.candidates = {}
        previous = candidates.get(match_id, _UNSET)
        candidates[match_id] = (config, calibration)
        try:
            yield
        finally:
            if previous is _UNSET:
                candidates.pop(match_id, None)
            else:
                candidates[match_id] = previous

    def calibration(self, match_id):
        root = self.root(match_id)
        if not (root / "current_generation.json").exists() and not (root / "generations").exists() and not (root / ".generation-format.json").exists():
            return _UNSET
        candidate = getattr(self.local, "candidates", {}).get(match_id)
        if candidate is not None:
            return candidate[1]
        try:
            with self.snapshot(match_id) as ref:
                manifest, _ = self.manifest(match_id, ref.generationId)
                if manifest.schemaVersion == 2:
                    return manifest.calibrationData
        except FileNotFoundError:
            pass
        return _UNSET

    def _commit_pointer(self, match_id, manifest, digest):
        root = self.root(match_id)
        pointer = {"schemaVersion": 2, "generationId": manifest.generationId,
                   "manifestSha256": digest, "publishedAt": manifest.publishedAt,
                   "correctionHead": manifest.correctionHead,
                   "calibrationRevision": manifest.calibrationRevision}
        fd, name = tempfile.mkstemp(prefix=".pointer-", dir=root)
        replaced = False
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(pointer, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, root / "current_generation.json")
            replaced = True
            _sync_directory(root)
        except BaseException as exc:
            if replaced:
                raise GenerationCommitUncertain(
                    f"Pointer {manifest.generationId} was replaced; explicit recovery required") from exc
            raise
        finally:
            Path(name).unlink(missing_ok=True)

    def refresh_index(self, match_id, manifest):
        directory = self.root(match_id) / "generations" / manifest.generationId
        summary = MatchSummary.model_validate(self._read(directory / "summary.json"))
        if manifest.algorithmVersions.get("legacy_import") and manifest.algorithmVersions["legacy_import"] != "3":
            # Rebuild the index with the same read semantics as the legacy API.
            # This is explicit maintenance, not a write performed by a GET.
            summary = self.storage.load_analytics(
                match_id, generation_id=manifest.generationId
            )[0]
        with self.storage._connect() as connection:
            row = connection.execute("SELECT config_json FROM matches WHERE id=?", (match_id,)).fetchone()
            if row is None:
                return
            config = json.loads(row["config_json"])
            if manifest.effectiveConfig is not None:
                config.update(manifest.effectiveConfig)
            connection.execute(
                "UPDATE matches SET analytics_summary_json=?, analytical_generation_id=?, "
                "semantic_config_revision=?, config_json=? WHERE id=?",
                (summary.model_dump_json(), manifest.generationId, manifest.semanticConfigRevision,
                 json.dumps(config), match_id))

    def command_metadata(self, match_id):
        history = [item for item in self.storage._load_correction_log(match_id).history(match_id)
                   if item.applyState in {"committed", "applying", "applied"}]
        commands = [{"commandId": item.commandId, "kind": item.kind, "payload": item.payload,
                     "version": item.version, "undoOf": item.undoOf} for item in history]
        return history, _digest(commands)

    def publish(self, match_id, *, frames, summary, assignments, formation_timeline,
                shots, events, correction_head, stale=None, orphaned_decisions=None,
                calibration_revision=None, effective_config=None, calibration_data=_UNSET,
                expected_parent=_UNSET, provenance=None, include_pending_commands=False):
        from .storage import _utcnow
        from .workbench.events import with_stable_event_id
        self.prepare(match_id)
        with self.guard(match_id, "review", exclusive=True), self.guard(match_id, "lifetime"):
            with self.guard(match_id, "publication"):
                try:
                    parent = self.resolve(match_id).generationId
                except FileNotFoundError:
                    parent = None
            planned_parent = parent if expected_parent is _UNSET else expected_parent
            if planned_parent != parent:
                raise StaleGeneration("Candidate was based on a stale generation")
            if effective_config is None and not (provenance and provenance.effectiveConfig is None):
                try:
                    effective_config = self.storage.get_match(match_id).config
                except KeyError:
                    effective_config = None
            effective = semantic_config(effective_config) if effective_config is not None else None
            if calibration_data is _UNSET:
                revision = self.storage.calibration_revision(match_id)
                calibration_data = revision.model_dump(mode="json") if revision else None
            if calibration_data is not None:
                calibration_revision = calibration_data.get("revisionId")
            summary = self.storage._video_ball_signal_summary(match_id, summary)
            if not any(a.team in {"my_team", "enemy"} for a in assignments):
                summary = summary.model_copy(update={"possession": None})
            analytics = {"summary": summary.model_dump(mode="json"),
                         "ballAssignments": [a.model_dump(mode="json") for a in assignments],
                         "formationTimeline": [f.model_dump(mode="json") for f in formation_timeline],
                         "shots": [s.model_dump(mode="json") for s in shots]}
            payloads = {"frames.json": [f.model_dump(mode="json") for f in frames],
                        "events.json": [with_stable_event_id(e).model_dump(mode="json") for e in events],
                        "analytics.json": analytics, "shots.json": analytics["shots"],
                        "summary.json": analytics["summary"]}
            if effective is not None:
                payloads["config.json"] = effective
            commands, command_digest = self.command_metadata(match_id)
            if any(c.applyState in {"committed", "applying"} for c in commands) and not include_pending_commands:
                raise StaleGeneration("Pending review commands require the canonical review materialiser")
            layered = self.storage._generation_layer_identities(
                match_id, calibration_revision=calibration_revision, correction_head=correction_head)
            gid = f"gen_{uuid.uuid4().hex}"
            directory = self.root(match_id) / "generations" / gid
            directory.mkdir(parents=True)
            self._receipt(self.root(match_id) / ".generation-format.json", {"schemaVersion": 2})
            for name, payload in payloads.items():
                self.storage._write_json(directory / name, payload)
                if name == "events.json":
                    self.storage._review_test_fault("during_generation_write")
            previous = provenance.model_dump(mode="json") if provenance else {}
            observation_digest = previous.get("observationDigest")
            if observation_digest is None:
                for name in ("raw_rows.json", "review_base_frames.json"):
                    path = self.root(match_id) / name
                    if path.is_file():
                        observation_digest = self.storage._sha256_file(path)
                        break
            source_identity = previous.get("sourceIdentity")
            if source_identity is None:
                try:
                    path = self.storage.get_match_input_path(match_id)
                    source_identity = {"sha256": self.storage._sha256_file(path), "byteSize": path.stat().st_size}
                except (KeyError, OSError):
                    pass
            identities = {layer + "Identity": value.get("digest") if value.get("reusable") is True else None
                          for layer, value in layered.items()}
            if provenance is not None:
                # A replacement retains its upstream provenance. Downstream cache
                # identities are invalidated, never advertised as reusable for new bytes.
                identities = {key: previous.get(key) for key in ("detectionIdentity", "trackingIdentity")}
                identities.update(projectionIdentity=None, reviewedIdentity=None, reportIdentity=None)
            fields = {**previous, **identities,
                      "schemaVersion": 2, "matchId": match_id, "generationId": gid,
                      "parentGenerationId": parent, "sourceIdentity": source_identity,
                      "observationDigest": observation_digest, "effectiveConfig": effective,
                      "semanticConfigRevision": _digest(effective) if effective is not None else None,
                      "calibrationRevision": calibration_revision, "calibrationData": calibration_data,
                      "correctionHead": commands[-1].correctionId if commands else correction_head,
                      "commandSetDigest": command_digest, "includedCommandIds": [c.commandId for c in commands],
                      "algorithmVersions": {**previous.get("algorithmVersions", {}), "generation_protocol": "2"},
                      "files": {name: self.storage._sha256_file(directory / name) for name in payloads},
                      "fileMetadata": {name: {"byteSize": (directory / name).stat().st_size, "schema": name + ":1"}
                                       for name in payloads},
                      "stale": list(stale if stale is not None else previous.get("stale", [])),
                      "orphanedDecisions": list(orphaned_decisions if orphaned_decisions is not None else previous.get("orphanedDecisions", [])),
                      "artifactStates": {**previous.get("artifactStates", {}), **{name: "present" for name in payloads}},
                      "publishedAt": _utcnow().isoformat().replace("+00:00", "Z")}
            for name in fields["stale"]:
                fields["artifactStates"][name] = "stale"
            manifest = GenerationManifest.model_validate(fields)
            self.storage._write_json(directory / "manifest.json", manifest.model_dump(mode="json"))
            manifest, digest = self.verify(match_id, gid)
            _sync_directory(directory)
            _sync_directory(directory.parent)
            self.storage._review_test_fault("before_pointer_publish")
            deferred = getattr(self.local, "deferred", {}).get(match_id)
            if deferred is not None:
                if deferred.get("publication") is not None:
                    raise StaleGeneration("An import may publish only one analytical candidate")
                deferred["publication"] = (manifest, digest, planned_parent)
                return self.resolve(match_id, gid)
            return self._activate(match_id, manifest, digest, planned_parent)

    def _activate(self, match_id, manifest, digest, planned_parent):
        """Sole analytical commit, including the end of a local remote import."""
        recovery_required = False
        with self.guard(match_id, "publication", exclusive=True):
            try:
                actual_parent = self.resolve(match_id).generationId
            except FileNotFoundError:
                actual_parent = None
            except GenerationRecoveryRequired:
                if planned_parent is None and not (self.root(match_id) / "current_generation.json").exists():
                    actual_parent = None
                else:
                    raise
            if actual_parent != planned_parent:
                raise StaleGeneration("Committed parent changed during materialisation")
            self._commit_pointer(match_id, manifest, digest)
            try:
                self.storage._review_test_fault("after_pointer_publish")
                try:
                    self.refresh_index(match_id, manifest)
                except Exception:
                    recovery_required = True
                self.storage._review_test_fault("after_index_update")
            except BaseException as exc:
                raise GenerationCommitUncertain(
                    f"Generation {manifest.generationId} is committed; reconcile forward") from exc
        return self.resolve(match_id, manifest.generationId).model_copy(
            update={"recoveryRequired": recovery_required})

    @contextmanager
    def deferred_publication(self, match_id):
        """Import cleanup must succeed before activation, not roll back a commit.

        The enclosing caller holds review + shared lifetime, so no other writer
        or retention task can interleave. Readers of the prior snapshot can run.
        """
        deferred = getattr(self.local, "deferred", None)
        if deferred is None:
            deferred = self.local.deferred = {}
        if match_id in deferred:
            raise StaleGeneration("Nested import transactions are unsupported")
        state = deferred[match_id] = {}
        try:
            yield
            if state.get("publication") is not None:
                self._activate(match_id, *state["publication"])
        finally:
            deferred.pop(match_id, None)

    def repair_commands(self, match_id, manifest):
        if not manifest.includedCommandIds:
            return
        log = self.storage._load_correction_log(match_id)
        history, digest = self.command_metadata(match_id)
        included = set(manifest.includedCommandIds)
        by_id = {c.commandId: c for c in history}
        if not included <= by_id.keys():
            raise GenerationRecoveryRequired("Committed generation references missing commands")
        subset = [c for c in history if c.commandId in included]
        expected = _digest([{"commandId": c.commandId, "kind": c.kind, "payload": c.payload,
                             "version": c.version, "undoOf": c.undoOf} for c in subset])
        if expected != manifest.commandSetDigest:
            raise GenerationRecoveryRequired("Committed command digest mismatch")
        changed = False
        for command in subset:
            if command.applyState in {"committed", "applying"}:
                log.update(command.correctionId, applyState="applied", appliedGeneration=manifest.generationId, lastError=None)
                changed = True
        if changed:
            self.storage._save_correction_log(match_id, log)

    def recover(self, match_id, *, migrate=True):
        self.prepare(match_id)
        with self.guard(match_id, "review", exclusive=True), self.guard(match_id, "lifetime"), self.guard(match_id, "publication", exclusive=True):
            root = self.root(match_id)
            try:
                pointer = self._pointer(match_id)
            except FileNotFoundError:
                legacy = [root / name for name in ("frames.json", "events.json", "analytics.json")]
                if migrate and all(path.is_file() for path in legacy):
                    return self.migrate_legacy(match_id)
                if any(path.exists() for path in legacy):
                    raise GenerationRecoveryRequired("Incomplete legacy snapshot")
                return {"status": "not_ready", "matchId": match_id}
            manifest, digest = self.verify(match_id, pointer["generationId"], expected_digest=pointer.get("manifestSha256"))
            if not pointer.get("manifestSha256"):
                # Explicit v1 admission, not winner selection or ordinary-read repair.
                self._commit_pointer(match_id, manifest, digest)
            self.refresh_index(match_id, manifest)
            self.repair_commands(match_id, manifest)
            receipt = {"status": "reconciled", "matchId": match_id, "generationId": manifest.generationId,
                       "manifestSha256": digest, "schemaVersion": 2}
            self._receipt(root / ".generation-recovery.json", receipt)
            self._receipt(root / ".generation-format.json", {"schemaVersion": 2})
            return receipt

    def _receipt(self, path, receipt):
        if not path.exists() or self._read(path) != receipt:
            self.storage._write_json(path, receipt)

    def migrate_legacy(self, match_id):
        """Call only under explicit recovery locks. Preserve flat artifacts."""
        from .storage import _utcnow
        root = self.root(match_id)
        if (root / "current_generation.json").exists() or (root / ".generation-format.json").exists():
            raise GenerationRecoveryRequired("Legacy migration cannot replace established authority")
        analytics = self._read(root / "analytics.json")
        # Normalise only the new candidate, through the established read contract.
        # Original legacy files are retained byte-for-byte, including old defaults.
        summary, _, _, _ = self.storage.load_analytics(match_id)
        analytics = {**analytics, "summary": summary.model_dump(mode="json")}
        legacy_digests = {
            name: self.storage._sha256_file(root / name)
            for name in ("frames.json", "events.json", "analytics.json")
        }
        payloads = {"frames.json": self._read(root / "frames.json"), "events.json": self._read(root / "events.json"),
                    "analytics.json": analytics, "shots.json": analytics.get("shots", []), "summary.json": analytics.get("summary", {})}
        gid = "gen_legacy_" + _digest(payloads)[:24]
        directory = root / "generations" / gid
        directory.mkdir(parents=True, exist_ok=False)
        for name, value in payloads.items():
            self.storage._write_json(directory / name, value)
        manifest = GenerationManifest(
            schemaVersion=2, matchId=match_id, generationId=gid, observationDigest=None,
            correctionHead="none", algorithmVersions={"legacy_import": "3"},
            files={name: self.storage._sha256_file(directory / name) for name in payloads},
            fileMetadata={name: {"byteSize": (directory / name).stat().st_size, "schema": name + ":1"}
                          for name in payloads},
            artifactStates={"analytical_configuration": "unknown", "source_observations": "unknown"},
            publishedAt=_utcnow().isoformat().replace("+00:00", "Z"))
        self.storage._write_json(directory / "manifest.json", manifest.model_dump(mode="json"))
        manifest, digest = self.verify(match_id, gid)
        _sync_directory(directory)
        _sync_directory(directory.parent)
        self._commit_pointer(match_id, manifest, digest)
        self.refresh_index(match_id, manifest)
        receipt = {"status": "migrated", "matchId": match_id, "generationId": gid,
                   "legacyArtifactDigests": legacy_digests, "summaryNormalization": "legacy-read-contract:1",
                   "provenance": "legacy configuration/observations unknown; originals retained", "schemaVersion": 2}
        self._receipt(root / ".generation-migration.json", receipt)
        self._receipt(root / ".generation-format.json", {"schemaVersion": 2})
        return receipt

    def retention(self, match_id, *, apply=False, generation_ids=None, rollback_generation_id=None):
        with self.guard(match_id, "lifetime", exclusive=apply, blocking=not apply), self.guard(match_id, "publication", exclusive=apply):
            ref = self.resolve(match_id)
            manifest, _ = self.manifest(match_id, ref.generationId)
            protected = {ref.generationId}
            rollback = rollback_generation_id or manifest.parentGenerationId
            if rollback:
                protected.add(_identifier(rollback))
            root = self.root(match_id)
            # Conservative reference discovery in retained command/report/evidence JSON.
            def references(value):
                if isinstance(value, str) and value.startswith("gen_") and _ID.fullmatch(value):
                    protected.add(value)
                elif isinstance(value, dict):
                    for v in value.values():
                        references(v)
                elif isinstance(value, list):
                    for v in value:
                        references(v)
            for path in root.rglob("*.json"):
                rel = path.relative_to(root)
                if rel.parts[0] in {"generations", ".generation-verified"} or path.name.startswith("."):
                    continue
                references(self._read(path))
            # Only proven ancestors are eligible. Failed/unpublished candidates stay retained.
            ancestors = set()
            parent = manifest.parentGenerationId
            while parent and parent not in ancestors:
                ancestors.add(parent)
                try:
                    previous, _ = self.manifest(match_id, parent)
                except GenerationRecoveryRequired:
                    break
                parent = previous.parentGenerationId
            eligible = ancestors - protected
            selected = eligible if generation_ids is None else {_identifier(gid) for gid in generation_ids}
            if selected - eligible:
                raise GenerationRecoveryRequired("Retention selected a protected, unknown or uncommitted generation")
            if apply:
                for gid in sorted(selected):
                    shutil.rmtree(root / "generations" / gid)
                    self._seal(match_id, gid).unlink(missing_ok=True)
                _sync_directory(root / "generations")
            return {"dryRun": not apply, "generationId": ref.generationId,
                    "protected": sorted(protected), "eligible": sorted(eligible),
                    "selected": sorted(selected), "removed": sorted(selected) if apply else []}
