"""Identity eligibility, repair, promotion, and continuity state behind the Storage facade."""

from __future__ import annotations


class _IdentityStorageMixin:
    def identity_eligibility(self, match_id: str, *, generation_id: str | None = None) -> dict:
        from .identity_eligibility import identity_eligibility
        try:
            with self.generation_snapshot(match_id, generation_id=generation_id) as ref:
                manifest, _ = self.generations.manifest(match_id, ref.generationId)
                result = identity_eligibility(manifest.identityContext)
                return {**result, "generationId": ref.generationId}
        except FileNotFoundError:
            return identity_eligibility(None)

    def _stored_identity_continuous(self, match_id: str) -> bool:
        return self.identity_eligibility(match_id)["continuous"]

    def _stored_calibration_accepted(self, match_id: str) -> bool:
        try:
            with self.generation_snapshot(match_id) as ref:
                manifest, _ = self.generations.manifest(match_id, ref.generationId)
                if manifest.identityContext is not None:
                    return manifest.identityContext.get("geometryEligible") is True
        except FileNotFoundError:
            pass
        revision = self.calibration_revision(match_id)
        return bool(revision and revision.accepted and revision.measured)

    def repair_identity_for_match(self, match_id: str, payload: dict | None = None) -> dict:
        from .workbench.identity import (
            frames_have_identity_overlap,
            rows_from_frames,
        )
        from .workbench.perception import IdentityRepair, preview_identity_change
        from .workbench.review import correction_api_payload

        self.get_match(match_id)
        body = dict(payload or {})
        kind = str(body.get("kind") or "track_split")
        track_id = str(body.get("trackId") or "")
        at_frame = int(body.get("atFrame") or 0)
        left_track_id = str(body.get("leftTrackId") or "")
        right_track_id = str(body.get("rightTrackId") or "")
        try:
            frames = self.load_frames(match_id)
        except FileNotFoundError:
            frames = []
        stored_ids = {str(row["trackId"]) for row in rows_from_frames(frames)}
        preview = preview_identity_change(
            kind=kind,
            track_id=track_id or None,
            at_frame=at_frame,
            interval_start=body.get("intervalStart"),
            interval_end=body.get("intervalEnd"),
        )
        known = False
        reason_codes: list[str] = []
        if kind == "track_split":
            known = track_id in stored_ids
        elif kind == "track_join":
            known = left_track_id in stored_ids and right_track_id in stored_ids
            if known and frames_have_identity_overlap(frames, left_track_id, right_track_id):
                known = False
                reason_codes.append("IDENTITY_OVERLAP")
        if not known and "IDENTITY_OVERLAP" not in reason_codes:
            reason_codes.append("UNKNOWN_TRACK")
        repair = IdentityRepair()
        if kind == "track_join":
            repair.join(left_track_id or "t-1", right_track_id or "t-2", author=str(body.get("author") or "analyst"))
        else:
            repair.split(track_id or "t-1", at_frame, author=str(body.get("author") or "analyst"))
        correction = None
        committed = False
        if kind in {"track_split", "track_join"} and (known or any(key in body for key in ("commandId", "idempotencyKey", "baseGeneration", "expectedVersion"))):
            payload = {
                "trackId": track_id,
                "atFrame": at_frame,
                "leftTrackId": left_track_id,
                "rightTrackId": right_track_id,
            }
            if "newTrackId" in body:
                payload["newTrackId"] = body["newTrackId"]
            saved = self.submit_correction(
                match_id,
                kind=kind,
                payload=payload,
                author=str(body.get("author") or "analyst"),
                expected_version=body.get("expectedVersion"),
                base_generation=body.get("baseGeneration"),
                command_id=body.get("commandId"),
                idempotency_key=body.get("idempotencyKey"),

            )
            correction = correction_api_payload(saved)
            committed = saved.applyState == "applied"
        return {
            **preview,
            "committed": committed,
            "identityContinuous": False,
            "silentlyReconnected": False,
            "visionRerun": False,
            "reasonCodes": reason_codes,
            "edits": repair.edits,
            "correction": correction,
            "storedTrack": known,
        }

    def promote_identity_for_match(self, match_id: str, payload: dict | None = None) -> dict:
        from .workbench.review import correction_api_payload

        self.get_match(match_id)
        body = dict(payload or {})
        reviewed = body.get("reviewed") is True
        reason_codes: list[str] = []
        correction = None
        committed = False
        if not reviewed:
            reason_codes.append("REVIEW_REQUIRED")
        else:
            saved = self.submit_correction(
                match_id,
                kind="identity_validate",
                payload={key: body[key] for key in ("reviewed", "identityRevision", "intervalStart", "intervalEnd", "trackIds", "teamScope") if key in body},
                author=str(body.get("author") or "analyst"),
                expected_version=body.get("expectedVersion"),
                base_generation=body.get("baseGeneration"),
                command_id=body.get("commandId"),
                idempotency_key=body.get("idempotencyKey"),

                crash_before_commit=bool(body.get("crashBeforeCommit")),
            )
            correction = correction_api_payload(saved)
            committed = saved.applyState == "applied"
        return {
            "preview": True,
            "committed": committed,
            "identityContinuous": self._stored_identity_continuous(match_id) if committed else False,
            "silentlyReconnected": False,
            "visionRerun": False,
            "reasonCodes": reason_codes,
            "correction": correction,
        }

    def _recompute_identity_continuity(self, match_id: str, *, identity_continuous: bool) -> None:
        from .analytics import summarize_match

        try:
            frames = self.load_frames(match_id)
            summary, assignments, timeline, shots = self.load_analytics(match_id)
        except FileNotFoundError:
            return
        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            events = []
        match = self.get_match(match_id)
        calibration = self.calibration_revision(match_id)
        self.save_analytics(
            match_id,
            summarize_match(
                frames,
                assignments,
                shots,
                events,
                attack_direction=match.config.attackDirection,
                identity_continuous=identity_continuous,
                calibration_accepted=bool(calibration and calibration.accepted and calibration.measured),
                pitch_length_m=(
                    calibration.pitchLengthM
                    if calibration is not None
                    else match.config.pitchLengthM or 105.0
                ),
                pitch_width_m=(
                    calibration.pitchWidthM
                    if calibration is not None
                    else match.config.pitchWidthM or 68.0
                ),
            ),
            assignments,
            timeline,
            shots,
        )

    def _apply_identity_edit(self, match_id: str, *, kind: str, payload: dict) -> None:
        from .workbench.identity import apply_track_join, apply_track_split, apply_track_unjoin, remap_track_references

        try:
            frames = self.load_frames(match_id)
        except FileNotFoundError:
            return
        at_frame = int(payload.get("atFrame") or 0)
        frame_ids = None
        if kind == "track_split":
            source = str(payload.get("trackId") or "")
            dest = int(payload["newTrackId"])
            frames = apply_track_split(frames, track_id=source, at_frame=at_frame, new_track_id=dest)
        elif kind == "track_join":
            source = str(payload.get("rightTrackId") or "")
            dest = int(payload.get("leftTrackId"))
            frames = apply_track_join(frames, left_track_id=str(dest), right_track_id=source)
            at_frame = 0
        elif kind == "track_join_undo":
            source = str(payload.get("leftTrackId") or "")
            dest = int(payload.get("rightTrackId"))
            frame_ids = [int(frame_id) for frame_id in payload.get("rightFrameIds") or []]
            if not frame_ids:
                return
            frames = apply_track_unjoin(
                frames,
                left_track_id=source,
                right_track_id=str(dest),
                right_frame_ids=frame_ids,
            )
            at_frame = 0
        else:
            return
        self.save_frames(match_id, frames)
        try:
            events = self.load_events(match_id)
        except FileNotFoundError:
            events = []
        if events:
            self.save_events(
                match_id,
                remap_track_references(
                    events,
                    track_id=source,
                    new_track_id=dest,
                    at_frame=at_frame,
                    frame_ids=frame_ids,
                ),
            )
        try:
            summary, assignments, timeline, shots = self.load_analytics(match_id)
        except FileNotFoundError:
            return
        self.save_analytics(
            match_id,
            summary,
            remap_track_references(
                assignments,
                track_id=source,
                new_track_id=dest,
                at_frame=at_frame,
                frame_ids=frame_ids,
            ),
            timeline,
            remap_track_references(
                shots,
                track_id=source,
                new_track_id=dest,
                at_frame=at_frame,
                frame_ids=frame_ids,
            ),
        )

    def _invalidate_stored_identity_continuity(self, match_id: str) -> None:
        try:
            summary, assignments, timeline, shots = self.load_analytics(match_id)
        except FileNotFoundError:
            return
        physical_names = {
            "my_team_distance_m",
            "enemy_distance_m",
            "my_team_top_speed_kmh",
            "enemy_top_speed_kmh",
            "my_team_sprints",
            "enemy_sprints",
        }
        availability = []
        for item in summary.metricAvailability:
            if item.metric in physical_names:
                reasons = list(item.reasonCodes or [])
                if "IDENTITY_DISCONTINUITY" not in reasons:
                    reasons.append("IDENTITY_DISCONTINUITY")
                availability.append(
                    item.model_copy(
                        update={"availability": "withheld", "value": None, "reasonCodes": reasons}
                    )
                )
            else:
                availability.append(item)
        self.save_analytics(
            match_id,
            summary.model_copy(
                update={
                    "metricAvailability": availability,
                    "myTeamDistance": None,
                    "enemyDistance": None,
                    "myTeamTopSpeed": None,
                    "enemyTopSpeed": None,
                    "myTeamSprints": None,
                    "enemySprints": None,
                }
            ),
            assignments,
            timeline,
            shots,
        )
