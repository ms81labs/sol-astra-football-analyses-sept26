from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from .processor import (
    _compute_outputs_and_match_state,
    _load_saved_ball_truth_layers,
    _normalize_match_state_evidence,
    reprocess_video_match,
)
from .analytics import build_shot_analytics, summarize_match
from .schemas import DetectedEvent, FrameData, MatchConfig
from .storage import Storage
from .workbench.errors import CorrectionApplicationError, StaleRevision
from .workbench.review import Correction, new_correction
from .workbench.events import apply_event_review, with_stable_event_id
from .workbench.identity import apply_remap, apply_team_swap, build_identity_remap


class ReviewService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def submit(
        self,
        match_id: str,
        *,
        kind: str,
        payload: dict,
        author: str,
        expected_version: int | None,
        base_generation: str | None,
        crash_before_commit: bool = False,
    ) -> Correction:
        correction = new_correction(match_id, kind, payload, author=author)  # type: ignore[arg-type]
        if base_generation is not None:
            correction = correction.model_copy(update={"baseGeneration": base_generation})
        with self._match_lock(match_id):
            with self.storage._annotation_issue_lock:
                log = self.storage._load_correction_log(match_id)
                saved = log.submit(
                    correction,
                    crash_before_commit=crash_before_commit,
                    expected_version=expected_version,
                )
                if saved.saveState == "conflicted":
                    actual = max((item.version for item in log.history(match_id)), default=0)
                    raise StaleRevision(expected=expected_version or 0, actual=actual)
                self.storage._save_correction_log(match_id, log)
            self._test_fault("after_log_commit")
            if saved.applyState == "committed":
                self._apply_pending_locked(match_id)
                saved = next(
                    item
                    for item in self.storage._load_correction_log(match_id).history(match_id)
                    if item.correctionId == saved.correctionId
                )
            return saved

    def recover(self, match_id: str, correction_id: str) -> Correction:
        with self._match_lock(match_id):
            with self.storage._annotation_issue_lock:
                log = self.storage._load_correction_log(match_id)
                saved = log.recover(correction_id)
                if saved.matchId != match_id:
                    raise KeyError(correction_id)
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

    def undo(self, match_id: str, correction_id: str, *, author: str) -> Correction:
        with self._match_lock(match_id):
            with self.storage._annotation_issue_lock:
                log = self.storage._load_correction_log(match_id)
                original = next((item for item in log.history(match_id) if item.correctionId == correction_id), None)
                if original is None:
                    raise KeyError(correction_id)
                command = new_correction(match_id, "undo", {"of": correction_id}, author=author).model_copy(
                    update={"undoOf": correction_id, "baseGeneration": self.storage.current_generation(match_id).generationId}
                )
                saved = log.submit(command)
                log.update(correction_id, supersededBy=saved.correctionId)
                self.storage._save_correction_log(match_id, log)
            self._test_fault("after_log_commit")
            self._apply_pending_locked(match_id)
            return next(
                item
                for item in self.storage._load_correction_log(match_id).history(match_id)
                if item.correctionId == saved.correctionId
            )

    def apply_pending(self, match_id: str) -> list[Correction]:
        with self._match_lock(match_id):
            return self._apply_pending_locked(match_id)

    def _apply_pending_locked(self, match_id: str) -> list[Correction]:
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
            for item in pending:
                log.update(item.correctionId, applyState="failed", lastError=str(exc))
            self.storage._save_correction_log(match_id, log)
            raise CorrectionApplicationError(pending[0].commandId, str(exc)) from exc
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
        current = self.storage.current_generation(match_id)
        commands = self._active_commands(match_id)
        effective_config = self._effective_config(match_id, commands)
        previous_config = self.storage.get_match(match_id).config
        previous_calibration = self.storage.calibration_revision(match_id)
        try:
            self.storage.update_match_config(match_id, effective_config)
            self._apply_auxiliary_state(match_id, commands)
            output = self._materialize(match_id, effective_config, commands)
            events = [with_stable_event_id(event) for event in output["events"]]
            orphaned_decisions: list[str] = []
            for command in commands:
                if command.kind not in {"event_accept", "event_reject"}:
                    continue
                events, previous = apply_event_review(
                    events,
                    kind=command.kind,
                    payload=command.payload,
                    match_id=match_id,
                )
                if not previous:
                    orphaned_decisions.append(str(command.payload.get("eventId") or command.correctionId))
            reviewed_events = [event for event in events if event.reviewStatus == "accepted"]
            shots = build_shot_analytics(
                output["frames"],
                reviewed_events,
                attack_direction=effective_config.attackDirection,
            )
            calibration = self.storage.calibration_revision(match_id)
            summary = summarize_match(
                output["frames"],
                output["assignments"],
                shots,
                reviewed_events,
                attack_direction=effective_config.attackDirection,
                identity_continuous=any(command.kind == "identity_validate" for command in commands),
                calibration_accepted=bool(calibration and calibration.accepted and calibration.measured),
                pitch_length_m=(
                    calibration.pitchLengthM
                    if calibration is not None
                    else effective_config.pitchLengthM or 105.0
                ),
                pitch_width_m=(
                    calibration.pitchWidthM
                    if calibration is not None
                    else effective_config.pitchWidthM or 68.0
                ),
            )
            head = commands[-1].correctionId if commands else current.correctionHead
            return self.storage.publish_generation(
                match_id,
                frames=output["frames"],
                summary=summary,
                assignments=output["assignments"],
                formation_timeline=output["formationTimeline"],
                shots=shots,
                events=events,
                correction_head=head,
                stale=(
                    ["pitch_positions", "physical_metrics", "tactical_metrics", "report"]
                    if reason == "calibration"
                    else ["tactical_report", "drills"]
                ),
                orphaned_decisions=orphaned_decisions,
                calibration_revision=None if calibration is None else calibration.revisionId,
            )
        except BaseException:
            self.storage.update_match_config(match_id, previous_config)
            self.storage._restore_calibration_revision(
                match_id,
                None if previous_calibration is None else previous_calibration.model_dump(mode="json"),
            )
            raise

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
    ) -> dict:
        match = self.storage.get_match(match_id)
        if match.inputMode == "video":
            base_output = reprocess_video_match(
                self.storage,
                match_id,
                config=config,
                persist=False,
            )
            frames = base_output["frames"]
        else:
            base_path = self.storage._match_dir(match_id) / "review_base_frames.json"
            if base_path.exists():
                frames = [FrameData.model_validate(item) for item in self.storage._read_json(base_path)]
            else:
                frames = self.storage.load_frames(match_id)
                self.storage._write_json(base_path, [frame.model_dump(mode="json") for frame in frames])
            swaps = sum(
                command.kind == "team_mapping" and command.payload.get("swap") is True
                for command in commands
            )
            if swaps % 2:
                frames = apply_team_swap(frames)
            calibration = self.storage.calibration_revision(match_id)
            if calibration is not None and calibration.accepted and calibration.measured:
                from .workbench.geometry import CalibrationProfile, project_tracking_frames

                frames = project_tracking_frames(
                    frames,
                    CalibrationProfile.model_validate(calibration.profile),
                    pitch_length_m=calibration.pitchLengthM,
                    pitch_width_m=calibration.pitchWidthM,
                )
        frames = apply_remap(frames, build_identity_remap(commands))
        ball_truth_layers = _load_saved_ball_truth_layers(self.storage, match_id)
        match_state_evidence = _normalize_match_state_evidence(frames, ball_truth_layers=ball_truth_layers)
        enriched, summary, events, assignments, formations, shots, accepted = _compute_outputs_and_match_state(
            frames,
            attack_direction=config.attackDirection,
            ball_truth_layers=ball_truth_layers,
            match_state_evidence=match_state_evidence,
        )
        return {
            "frames": enriched,
            "summary": summary,
            "events": events,
            "assignments": assignments,
            "formationTimeline": formations,
            "shots": shots,
            "acceptedMatchState": accepted,
            "requiresTeamSelection": match.requiresTeamSelection,
        }

    def _active_commands(self, match_id: str) -> list[Correction]:
        history = self.storage._load_correction_log(match_id).history(match_id)
        included = [item for item in history if item.applyState in {"applied", "applying"}]
        undone = {
            str(item.payload.get("of"))
            for item in included
            if item.kind == "undo" and item.payload.get("of")
        }
        return [item for item in included if item.kind != "undo" and item.correctionId not in undone]

    def _effective_config(self, match_id: str, commands: list[Correction]) -> MatchConfig:
        match_dir = self.storage._match_dir(match_id)
        base_path = match_dir / "review_base_config.json"
        if base_path.exists():
            base_config = MatchConfig.model_validate(self.storage._read_json(base_path))
        else:
            base_config = self.storage.get_match(match_id).config
            self.storage._write_json(base_path, base_config.model_dump(mode="json"))
        current_config = self.storage.get_match(match_id).config
        config = current_config.model_copy(update={"myTeamCluster": base_config.myTeamCluster})
        cluster_ids = sorted(cluster.clusterId for cluster in self.storage.get_match(match_id).teamClusters)
        for command in commands:
            if command.kind != "team_mapping" or command.payload.get("swap") is not True:
                continue
            alternatives = [cluster_id for cluster_id in cluster_ids if cluster_id != config.myTeamCluster]
            if alternatives:
                config = config.model_copy(update={"myTeamCluster": alternatives[0]})
        return config

    @contextmanager
    def _match_lock(self, match_id: str) -> Iterator[None]:
        path = self.storage._match_dir(match_id) / ".review.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+b") as handle:
            try:
                import fcntl
            except ImportError:
                with self.storage._annotation_issue_lock:
                    yield
                return
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _test_fault(point: str) -> None:
        if os.environ.get("GA_TEST_FAULTS") == "1" and os.environ.get("GA_TEST_FAULT_POINT") == point:
            os._exit(1)
