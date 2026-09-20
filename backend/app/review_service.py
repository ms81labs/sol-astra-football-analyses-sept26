from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from .processor import (
    _load_saved_ball_truth_layers,
    _normalize_match_state_evidence,
    load_video_source_frames,
)
from .schemas import MatchConfig
from .storage import Storage
from .workbench.errors import CorrectionApplicationError, StaleRevision, IdempotencyConflict
from .semantic_commands import (
    ANALYTICAL_FIELDS, POLICY_FIELDS, METADATA_FIELDS, CONTROL_FIELDS,
    SemanticCommandError, active_commands, canonical_team_mapping, digest,
    validate_cluster, validate_config_values, validate_undo,
)
from .workbench.review import Correction, new_correction
from .workbench.identity import apply_remap, apply_team_swap, build_identity_remap


class ReviewService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def submit(
        self, match_id: str, *, kind: str, payload: dict, author: str,
        expected_version: int | None, base_generation: str | None,
        crash_before_commit: bool = False, command_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Correction:
        from .generations import StaleGeneration

        if not isinstance(payload, dict):
            raise SemanticCommandError("INVALID_COMMAND_PAYLOAD", "Command payload must be an object")
        if base_generation is not None and (not isinstance(base_generation, str) or not base_generation):
            raise SemanticCommandError("INVALID_BASE_GENERATION", "baseGeneration must be a nonempty generation ID")
        if expected_version is not None and (type(expected_version) is not int or expected_version < 0):
            raise SemanticCommandError("INVALID_EXPECTED_VERSION", "expectedVersion must be a nonnegative integer")
        for key in (command_id, idempotency_key):
            if key is not None and (not isinstance(key, str) or not key.strip() or len(key) > 160):
                raise SemanticCommandError("INVALID_COMMAND_ID", "Command identifiers must be nonempty strings of at most 160 characters")
        try:
            request_digest = digest({"kind": kind, "payload": {k: v for k, v in payload.items() if k != "previous"},
                                     "author": author, "expectedVersion": expected_version, "baseGeneration": base_generation,
                                     "commandId": command_id, "idempotencyKey": idempotency_key})
        except (TypeError, ValueError) as exc:
            raise SemanticCommandError("INVALID_COMMAND_PAYLOAD", "Command must contain finite JSON values") from exc
        with self._match_lock(match_id):
            log = self.storage._load_correction_log(match_id)
            history = log.history(match_id)
            for existing in [*history, *log.pending(match_id)]:
                if ((command_id is not None and existing.commandId == command_id)
                        or (idempotency_key is not None and existing.idempotencyKey == idempotency_key)):
                    if existing.requestDigest != request_digest:
                        raise IdempotencyConflict(command_id or idempotency_key or "")
                    # An idempotent replay is a receipt lookup, not another apply/retry.
                    return existing
            actual_version = max((item.version for item in history), default=0)
            if expected_version is not None and actual_version != expected_version:
                raise StaleRevision(expected=expected_version, actual=actual_version)
            try:
                current = self.storage.current_generation(match_id).generationId
            except FileNotFoundError:
                current = None
            if base_generation is not None and base_generation != current:
                raise StaleGeneration("Command was based on a stale generation")
            match = self.storage.get_match(match_id)
            if kind in {"config_set", "team_mapping"} and (
                match.status == "processing" or self.storage.has_active_job(match_id)
            ):
                raise SemanticCommandError("MATCH_PROCESSING", "Finish processing before changing analytical inputs", status_code=409)
            canonical = self._validate_command(match_id, kind, payload, history, author=author)
            correction = new_correction(match_id, kind, canonical, author=author).model_copy(update={
                "schemaVersion": 2, "baseGeneration": current, "requestDigest": request_digest,
                "idempotencyKey": idempotency_key,
                **({"commandId": command_id} if command_id is not None else {}),
                **({"undoOf": canonical["of"]} if kind == "undo" else {}),
            })
            # Freeze base inputs only after every admission check passes. This is a
            # semantic write operation; routine GETs never create these files.
            self._ensure_base(match_id)
            with self.storage._annotation_issue_lock:
                saved = log.submit(correction, crash_before_commit=crash_before_commit,
                                   expected_version=expected_version)
                self.storage._save_correction_log(match_id, log)
            self._test_fault("after_log_commit")
            if saved.applyState == "committed":
                self._apply_pending_locked(match_id)
                saved = next(c for c in self.storage._load_correction_log(match_id).history(match_id)
                             if c.correctionId == saved.correctionId)
            return saved

    def configure(self, match_id: str, body: dict) -> tuple[MatchConfig, Correction | None]:
        """Existing config PATCH, with analytical changes admitted as commands.

        Mixed analytical/policy requests are explicitly refused, even if some
        values happen to equal their current value. No partial consent update.
        """
        if not isinstance(body, dict) or set(body) - (ANALYTICAL_FIELDS | POLICY_FIELDS | METADATA_FIELDS | CONTROL_FIELDS):
            raise SemanticCommandError("INVALID_CONFIG_FIELD", "Unknown or server-owned configuration field")
        values = {k: v for k, v in body.items() if k not in CONTROL_FIELDS}
        analytical = {k: v for k, v in values.items() if k in ANALYTICAL_FIELDS}
        if analytical and (set(values) & (POLICY_FIELDS | METADATA_FIELDS)):
            raise SemanticCommandError("MIXED_CONFIG_UPDATE", "Submit analytical and policy/metadata updates separately")
        with self._match_lock(match_id):
            match = self.storage.get_match(match_id)
            config = MatchConfig.model_validate({**match.config.model_dump(mode="python"), **values}, strict=True)
            if analytical:
                try:
                    before_generation = self.storage.current_generation(match_id).generationId
                except FileNotFoundError as exc:
                    raise SemanticCommandError("ANALYTICS_NOT_READY", "An analytical edit requires a complete source generation", status_code=409) from exc
                saved = self.submit(match_id, kind="config_set", payload={"values": analytical}, author="analyst",
                                    expected_version=body.get("expectedVersion"), base_generation=body.get("baseGeneration"),
                                    command_id=body.get("commandId"), idempotency_key=body.get("idempotencyKey"))
                after_generation = self.storage.current_generation(match_id).generationId
                if saved.applyState == "applied" and after_generation != before_generation:
                    # Preserve the established current-report invalidation path.
                    # C03 supplies generation-bound historical report readers.
                    self.storage.invalidate_coach_analysis(match_id)
                return self.storage.get_match(match_id).config, saved
            if values:
                self.storage.update_match_config(match_id, config)
            return self.storage.get_match(match_id).config, None

    def _validate_command(self, match_id: str, kind: str, payload: dict, history: list[Correction], *, author: str = "analyst") -> dict:
        match = self.storage.get_match(match_id)
        if kind in {"team_mapping", "config_set", "undo"}:
            # Fail ambiguous legacy replay before appending a new command.
            self._effective_config(match_id, active_commands(history))
        if kind in {"event_accept", "event_reject"}:
            return {**payload, "previous": self.storage._event_review_snapshot(match_id, payload)}
        if kind == "config_set":
            if set(payload) != {"values"}:
                raise SemanticCommandError("INVALID_SEMANTIC_CONFIG", "config_set requires only values")
            values = validate_config_values(payload["values"], match.config)
            calibration = self.storage.calibration_revision(match_id)
            if calibration is not None and calibration.accepted and calibration.measured:
                live = match.config.model_dump(mode="json")
                if any(field in values and values[field] != live[field]
                       for field in ("manualHomographyPoints", "cameraProfile")):
                    raise SemanticCommandError("CALIBRATION_COMMIT_REQUIRED",
                        "Changing calibrated camera inputs requires a validated calibration commit")
                if any(field in values and values[field] != getattr(calibration, field)
                       for field in ("pitchLengthM", "pitchWidthM")):
                    raise SemanticCommandError("CALIBRATION_COMMIT_REQUIRED",
                        "Change calibrated pitch dimensions through a validated calibration commit")
            if "myTeamCluster" in values:
                validate_cluster(values["myTeamCluster"], {c.clusterId for c in match.teamClusters})
            return {"values": values}
        if kind == "team_mapping":
            return canonical_team_mapping(payload, clusters={c.clusterId for c in match.teamClusters},
                                          selected=match.config.myTeamCluster,
                                          tracking_role=self._tracking_role(match_id, active_commands(history)),
                                          input_mode=match.inputMode)
        if kind == "calibration" and set(payload) == {"profile"}:
            from .workbench.geometry import CalibrationProfile, commit_calibration
            profile = CalibrationProfile.model_validate(payload["profile"])
            result = commit_calibration(profile)
            if not result.get("committed"):
                raise SemanticCommandError("CALIBRATION_REJECTED", "A measured supported calibration is required")
            previous = self.storage.calibration_revision(match_id)
            revision = self.storage._new_calibration_revision(match_id, profile=result["profile"],
                evaluation={**dict(result["evaluation"]), "measured": True})
            return {"revision": revision, "previousRevision": previous.model_dump(mode="json") if previous else None}
        if kind == "identity_validate":
            from .identity_eligibility import approval_payload
            return approval_payload(self.storage, match_id, payload, history, author=author)
        if kind == "undo":
            if set(payload) != {"of"} or not isinstance(payload["of"], str):
                raise SemanticCommandError("INVALID_UNDO", "Undo requires one command ID")
            original = next((c for c in history if c.correctionId == payload["of"]), None)
            if original is None:
                raise KeyError(payload["of"])
            validate_undo(original, history)
        if kind in {"track_split", "track_join"}:
            from .workbench.identity import frames_with_track, frames_have_identity_overlap, next_available_track_id
            frames = self.storage.load_frames(match_id)
            if kind == "track_split":
                source, dest, at = str(payload.get("trackId", "")), payload.get("newTrackId", next_available_track_id(frames)), payload.get("atFrame")
                if type(dest) is not int or type(at) is not int or at < 0 or dest < 0:
                    raise SemanticCommandError("INVALID_TRACK_SPLIT", "Split requires integer frame and destination ID")
                if not any(f >= at for f in frames_with_track(frames, source)) or frames_with_track(frames, str(dest)):
                    raise SemanticCommandError("INVALID_TRACK_SPLIT", "Split source must exist and its destination must be unused")
                return {**payload, "newTrackId": dest}
            else:
                left, right = str(payload.get("leftTrackId", "")), str(payload.get("rightTrackId", ""))
                if left == right or not frames_with_track(frames, left) or not frames_with_track(frames, right):
                    raise SemanticCommandError("UNKNOWN_TRACK", "Both distinct join tracks must exist")
                if frames_have_identity_overlap(frames, left, right):
                    raise SemanticCommandError("IDENTITY_OVERLAP", "Overlapping tracks cannot be joined")
                return {**payload, "rightFrameIds": frames_with_track(frames, right)}
        return dict(payload)

    def _ensure_base(self, match_id: str) -> None:
        path = self.storage._match_dir(match_id) / "review_base_config.json"
        if not path.exists():
            from .generations import semantic_config
            self.storage._write_json(path, semantic_config(self.storage.get_match(match_id).config))
        if self.storage.get_match(match_id).inputMode == "video":
            legacy = [c for c in self._active_commands(match_id)
                      if c.schemaVersion == 1 and c.kind == "team_mapping" and c.payload.get("swap") is True]
            if legacy:
                records = {c.commandId: {"payloadDigest": digest(c.payload),
                    "appliedGeneration": c.appliedGeneration, "targetCluster": self._legacy_video_target(match_id, c)} for c in legacy}
                receipt = self.storage._match_dir(match_id) / "review_command_migrations.json"
                previous = self.storage._read_json(receipt) if receipt.exists() else {"schemaVersion": 1, "resolved": {}}
                merged = {**previous, "resolved": {**previous["resolved"], **records}}
                if merged != previous:
                    self.storage._write_json(receipt, merged)

    def recover(self, match_id: str, correction_id: str) -> Correction:
        with self._match_lock(match_id):
            with self.storage._annotation_issue_lock:
                log = self.storage._load_correction_log(match_id)
                item = next((c for c in [*log.history(match_id), *log.pending(match_id)]
                             if c.correctionId == correction_id), None)
                if item is None or item.matchId != match_id:
                    raise KeyError(correction_id)
                if item.applyState in {"received", "failed"}:
                    from .generations import StaleGeneration
                    current = self.storage.current_generation(match_id).generationId
                    if item.schemaVersion == 2 and item.baseGeneration != current:
                        raise StaleGeneration("Unapplied request no longer matches its source generation")
                saved = log.recover(correction_id)
                if saved.applyState == "failed":
                    saved = log.update(correction_id, applyState="committed", lastError=None)
                self.storage._save_correction_log(match_id, log)
            if saved.applyState == "committed":
                self._apply_pending_locked(match_id)
            return next(
                item
                for item in self.storage._load_correction_log(match_id).history(match_id)
                if item.correctionId == correction_id
            )

    def undo(self, match_id: str, correction_id: str, *, author: str,
             expected_version: int | None = None, base_generation: str | None = None,
             command_id: str | None = None, idempotency_key: str | None = None) -> Correction:
        return self.submit(match_id, kind="undo", payload={"of": correction_id}, author=author,
                           expected_version=expected_version, base_generation=base_generation,
                           command_id=command_id, idempotency_key=idempotency_key)

    def apply_pending(self, match_id: str) -> list[Correction]:
        with self._match_lock(match_id):
            return self._apply_pending_locked(match_id)

    def _apply_pending_locked(self, match_id: str) -> list[Correction]:
        try:
            current = self.storage.current_generation(match_id)
        except FileNotFoundError:
            current = None
        if current is not None:
            manifest, _ = self.storage.generations.manifest(match_id, current.generationId)
            self.storage.generations.repair_commands(match_id, manifest)
        log = self.storage._load_correction_log(match_id)
        pending = [
            item for item in log.history(match_id) if item.applyState in {"committed", "applying"}
        ]
        if not pending:
            return []
        for item in pending:
            log.update(item.correctionId, applyState="applying", attempts=item.attempts + 1)
        self.storage._save_correction_log(match_id, log)
        try:
            ref = self.rebuild_generation(
                match_id,
                reason="calibration" if any(item.kind == "calibration" for item in pending) else "correction",
            )
        except Exception as exc:
            from .generations import GenerationCommitUncertain
            if isinstance(exc, GenerationCommitUncertain):
                raise  # Leave commands applying; recovery must inspect the pointer.
            for item in pending:
                log.update(item.correctionId, applyState="failed", lastError=str(exc))
            self.storage._save_correction_log(match_id, log)
            if isinstance(exc, SemanticCommandError):
                raise
            if isinstance(exc, FileNotFoundError):
                raise SemanticCommandError("SOURCE_OBSERVATIONS_REQUIRED", "Required source observations are unavailable", status_code=409) from exc
            raise CorrectionApplicationError(pending[0].commandId, str(exc)) from exc
        self._test_fault("before_applied_marker")
        applied = []
        for item in pending:
            applied.append(
                log.update(
                    item.correctionId,
                    applyState="applied",
                    appliedGeneration=ref.generationId,
                    lastError=None,
                )
            )
        self.storage._save_correction_log(match_id, log)
        return applied

    def rebuild_generation(self, match_id: str, *, reason: str):
        return self.materialize_and_publish(match_id, reason=reason)[0]

    def materialize_and_publish(self, match_id: str, *, reason: str, team_clusters=None, match_state_evidence=None, prepared_frames=None):
        with self._match_lock(match_id):
            return self._rebuild_generation_locked(match_id, reason=reason, team_clusters=team_clusters,
                                                   match_state_evidence=match_state_evidence, prepared_frames=prepared_frames)

    def _rebuild_generation_locked(self, match_id: str, *, reason: str, team_clusters=None, match_state_evidence=None, prepared_frames=None):
        try:
            current = self.storage.current_generation(match_id)
        except FileNotFoundError:
            current = None
        commands = self._active_commands(match_id)
        effective_config = self._effective_config(match_id, commands)
        previous_calibration = self.storage.calibration_revision(match_id)
        calibration_data = None if previous_calibration is None else previous_calibration.model_dump(mode="json")
        active_calibrations = [command for command in commands if command.kind == "calibration"]
        if active_calibrations:
            calibration_data = active_calibrations[-1].payload.get("revision")
        else:
            history = [command for command in self.storage._load_correction_log(match_id).history(match_id)
                       if command.kind == "calibration"]
            if history:
                calibration_data = history[0].payload.get("previousRevision")
        if calibration_data is not None:
            # Preprocessing calibration has no command yet. Its dimensions are
            # still explicit candidate inputs, not mutable live defaults.
            dimensions = {field: calibration_data[field] for field in ("pitchLengthM", "pitchWidthM")
                          if getattr(effective_config, field) is None}
            effective_config = effective_config.model_copy(update=dimensions)
        with self.storage.generations.candidate(match_id, effective_config, calibration_data):
            options = {}
            if team_clusters is not None:
                options["team_clusters"] = team_clusters
            if match_state_evidence is not None:
                options["match_state_evidence"] = match_state_evidence
            if prepared_frames is not None and current is None and not commands and calibration_data is None:
                # Trusted post-perception input from the processor; only valid
                # for the initial uncalibrated publication at this configuration.
                options["prepared_frames"] = prepared_frames
            output = self._materialize(match_id, effective_config, commands, **options)
            calibration = self.storage.calibration_revision(match_id)
            ref = self.storage.publish_generation(
                match_id, frames=output["frames"], summary=output["summary"], assignments=output["assignments"],
                formation_timeline=output["formationTimeline"], shots=output["shots"], events=output["events"],
                correction_head=commands[-1].correctionId if commands else current.correctionHead if current else "none",
                stale=["tactical_report", "drills", "report"],
                orphaned_decisions=output["acceptedMatchState"].get("orphanedDecisions", []),
                calibration_revision=None if calibration is None else calibration.revisionId,
                calibration_data=calibration_data, effective_config=effective_config,
                expected_parent=current.generationId if current else None, include_pending_commands=True,
                identity_context=output["identityContext"],
            )
            return ref, output

    def _apply_auxiliary_state(self, match_id: str, commands: list[Correction]) -> None:
        active_calibrations = [command for command in commands if command.kind == "calibration"]
        if active_calibrations:
            revision = active_calibrations[-1].payload.get("revision")
            if isinstance(revision, dict):
                self.storage._save_calibration_revision(match_id, revision)
            return
        calibration_history = [
            command
            for command in self.storage._load_correction_log(match_id).history(match_id)
            if command.kind == "calibration"
        ]
        if calibration_history:
            previous = calibration_history[0].payload.get("previousRevision")
            self.storage._restore_calibration_revision(
                match_id, previous if isinstance(previous, dict) else None
            )

    def _materialize(
        self,
        match_id: str,
        config: MatchConfig,
        commands: list[Correction],
        *, team_clusters=None, match_state_evidence=None, prepared_frames=None,
    ) -> dict:
        match = self.storage.get_match(match_id)
        if match.inputMode == "video":
            if prepared_frames is not None:
                from .processor import _resolve_selected_cluster
                frames = prepared_frames
                requires_selection = _resolve_selected_cluster(config, team_clusters or [])[1]
                provenance = {"schemaVersion": 1, "migration": "guerilla_video_rows_v1:legacy_pitch_view",
                              "reasonCodes": ["CALIBRATION_REQUIRED"]}
                # These are owned transient normalized frames, not persisted
                # observations. Sharing the constant descriptor avoids O(n)
                # duplicate dictionaries during large streaming imports.
                for frame in frames:
                    frame.geometryAvailable = False
                    frame.coordinateProvenance = provenance
            else:
                frames, requires_selection = load_video_source_frames(self.storage, match_id, config=config, team_clusters=team_clusters)
        else:
            requires_selection = False
            from .coordinates import import_tracking, project_tracking
            source_path = self.storage.get_match_input_path(match_id)
            base_path = self.storage._match_dir(match_id) / "review_base_frames.json"
            payload = self.storage._read_json(source_path)
            if not payload and base_path.exists():
                payload = self.storage._read_json(base_path)
            elif not payload:
                try:
                    frames = self.storage.load_frames(match_id)
                except FileNotFoundError:
                    frames = []
                payload = [frame.model_dump(mode="json") for frame in frames]
                if frames:
                    self.storage._write_json(base_path, payload)
            frames, convention, migration = import_tracking(payload, convention=config.coordinateConvention)
            calibration = self.storage.calibration_revision(match_id)
            if calibration is not None and calibration.sourceSha256 != self.storage.source_sha256(match_id):
                raise SemanticCommandError("CALIBRATION_SOURCE_MISMATCH", "Calibration belongs to another source", status_code=409)
            frames = project_tracking(frames, convention, calibration, migration=migration)
            if self._tracking_role(match_id, commands) == "enemy":
                frames = apply_team_swap(frames)
        frames = apply_remap(frames, build_identity_remap(commands))
        from .identity_eligibility import context_for, identity_eligibility
        identity_context = context_for(self.storage, match_id, frames, commands)
        identity_ok = identity_eligibility(identity_context)["continuous"]
        calibration = self.storage.calibration_revision(match_id)
        geometry_ok = bool(calibration and calibration.accepted and calibration.measured
                           and frames and all(f.geometryAvailable for f in frames))
        if geometry_ok:
            from .coordinates import _covered
            from .workbench.geometry import CalibrationProfile
            profile = CalibrationProfile.model_validate(calibration.profile)
            geometry_ok = all(_covered(profile, calibration, f.timestamp) for f in frames)
            from .workbench.media import detect_camera_cuts
            # Use the distance endpoint's existing discontinuity rule for all
            # physical consumers. One point or a cut cannot establish movement.
            has_step = any(
                frame.timestamp > previous.timestamp and any(
                    {player.id for player in getattr(previous, field)} &
                    {player.id for player in getattr(frame, field)}
                    for field in ("myTeam", "enemies")
                )
                for previous, frame in zip(frames, frames[1:])
            )
            cuts = detect_camera_cuts([frame.timestamp for frame in frames])
            identity_context["geometryReasonCodes"] = (
                ([] if has_step else ["ZERO_DENOMINATOR"])
                + (["CAMERA_CUT"] if cuts else [])
                + ([] if geometry_ok else ["CALIBRATION_INTERVAL_UNAVAILABLE"])
            )
            geometry_ok = geometry_ok and has_step and not cuts
            # A declaration in metres and the accepted calibration must describe
            # the same pitch; do not silently rescale physical quantities.
            for name in ("pitchLengthM", "pitchWidthM"):
                requested = getattr(config, name)
                if requested is not None and requested != getattr(calibration, name):
                    raise SemanticCommandError("PITCH_DIMENSIONS_MISMATCH", "Analytical and calibration pitch dimensions differ", status_code=409)
            for frame in frames:
                declared = frame.coordinateProvenance.get("inputConvention", {})
                if declared.get("space") == "pitch_metres" and any(
                    declared.get(name) != getattr(calibration, name) for name in ("pitchLengthM", "pitchWidthM")
                ):
                    raise SemanticCommandError("PITCH_DIMENSIONS_MISMATCH", "Tracking and calibration pitch dimensions differ", status_code=409)
        identity_context["geometryEligible"] = geometry_ok
        ball_truth_layers = _load_saved_ball_truth_layers(self.storage, match_id)
        # Old flat ball-state coordinates cannot be reused under a new transform.
        if calibration is not None:
            ball_truth_layers = None
            match_state_evidence = None
        match_state_evidence = _normalize_match_state_evidence(frames, ball_truth_layers=ball_truth_layers,
                                                              match_state_evidence=match_state_evidence)
        from . import processor

        enriched, summary, events, assignments, formations, shots, accepted = processor._compute_outputs_and_match_state(
            frames,
            attack_direction=config.attackDirection,
            ball_truth_layers=ball_truth_layers,
            match_state_evidence=match_state_evidence,
            review_commands=commands,
            summary_options={"identity_continuous":identity_ok, "calibration_accepted":geometry_ok,
                             "pitch_length_m":calibration.pitchLengthM if calibration else config.pitchLengthM or 105.,
                             "pitch_width_m":calibration.pitchWidthM if calibration else config.pitchWidthM or 68.},
        )
        if not geometry_ok:
            summary = summary.model_copy(update={key: None for key in (
                "myTeamDistance", "enemyDistance", "myTeamTopSpeed", "enemyTopSpeed", "myTeamSprints", "enemySprints")})
        return {
            "identityContext": identity_context,
            "identityEligible": identity_ok,
            "geometryEligible": geometry_ok,
            "frames": enriched,
            "summary": summary,
            "events": events,
            "assignments": assignments,
            "formationTimeline": formations,
            "shots": shots,
            "acceptedMatchState": accepted,
            "requiresTeamSelection": requires_selection,
        }

    def _active_commands(self, match_id: str) -> list[Correction]:
        return active_commands(self.storage._load_correction_log(match_id).history(match_id))

    def _effective_config(self, match_id: str, commands: list[Correction]) -> MatchConfig:
        from .generations import semantic_config
        base_path = self.storage._match_dir(match_id) / "review_base_config.json"
        live = self.storage.get_match(match_id).config
        base = self.storage._read_json(base_path) if base_path.exists() else semantic_config(live)
        # Every analytical field is replayed from the frozen base; current rights
        # and display names always come from live state, not the historical file.
        effective = {**live.model_dump(mode="json"), **semantic_config(base)}
        for command in commands:
            if command.kind == "config_set":
                values = command.payload.get("values", {})
                if not isinstance(values, dict) or set(values) - ANALYTICAL_FIELDS:
                    raise SemanticCommandError("INVALID_SEMANTIC_CONFIG", "Invalid stored analytical command", status_code=409)
                effective.update(values)
            elif command.kind == "calibration":
                revision = command.payload.get("revision")
                if isinstance(revision, dict):
                    effective.update({field: revision[field] for field in ("pitchLengthM", "pitchWidthM")})
            elif command.kind == "team_mapping":
                payload = command.payload
                if payload.get("operation") == "select_cluster":
                    effective["myTeamCluster"] = payload["targetCluster"]
                elif command.schemaVersion == 1 and payload.get("swap") is True:
                    match = self.storage.get_match(match_id)
                    if match.inputMode != "video":
                        continue
                    # An immutable applied snapshot is evidence of the old target.
                    # Never mutate its command payload or guess from today's clusters.
                    effective["myTeamCluster"] = self._legacy_video_target(match_id, command)
        return MatchConfig.model_validate(effective)

    def _legacy_video_target(self, match_id: str, command: Correction) -> int:
        if not command.appliedGeneration:
            raise SemanticCommandError("LEGACY_TEAM_MAPPING_REQUIRED", "Historical team mapping has no applied snapshot", status_code=409)
        with self.storage.generation_snapshot(match_id, generation_id=command.appliedGeneration) as ref:
            manifest, _ = self.storage.generations.manifest(match_id, ref.generationId)
            old = manifest.effectiveConfig
            siblings = [c for c in self.storage._load_correction_log(match_id).history(match_id)
                        if c.appliedGeneration == command.appliedGeneration
                        and c.kind in {"team_mapping", "config_set"}]
            if len(siblings) != 1:
                raise SemanticCommandError("LEGACY_TEAM_MAPPING_REQUIRED", "Grouped historical commands do not establish individual targets", status_code=409)
            # The generation must actually bind this command, not merely contain
            # a convenient selected-cluster value.
            if command.commandId not in manifest.includedCommandIds:
                raise SemanticCommandError("LEGACY_TEAM_MAPPING_REQUIRED", "Historical snapshot does not include the command", status_code=409)
            history = self.storage._load_correction_log(match_id).history(match_id)
            included = set(manifest.includedCommandIds)
            bound = [c for c in history if c.commandId in included]
            if digest([{"commandId": c.commandId, "kind": c.kind, "payload": c.payload,
                        "version": c.version, "undoOf": c.undoOf} for c in bound]) != manifest.commandSetDigest:
                raise SemanticCommandError("LEGACY_TEAM_MAPPING_REQUIRED", "Historical command digest mismatch", status_code=409)
        if old is None or type(old.get("myTeamCluster")) is not int:
            raise SemanticCommandError("LEGACY_TEAM_MAPPING_REQUIRED", "Historical target cannot be established", status_code=409)
        return old["myTeamCluster"]

    def _tracking_role(self, match_id: str, commands: list[Correction]) -> str:
        role = "my_team"
        for command in commands:
            if command.kind != "team_mapping":
                continue
            if command.payload.get("operation") == "select_role":
                role = command.payload["targetRole"]
            elif command.schemaVersion == 1 and command.payload.get("swap") is True:
                # The documented legacy tracking format has exactly two named
                # roles. This is not the ambiguous colour-cluster algorithm.
                role = "enemy" if role == "my_team" else "my_team"
        return role

    @contextmanager
    def _match_lock(self, match_id: str) -> Iterator[None]:
        self.storage.generations.prepare(match_id)
        with self.storage.generations.guard(match_id, "review", exclusive=True):
            yield

    @staticmethod
    def _test_fault(point: str) -> None:
        if os.environ.get("GA_TEST_FAULTS") == "1" and os.environ.get("GA_TEST_FAULT_POINT") == point:
            os._exit(1)
