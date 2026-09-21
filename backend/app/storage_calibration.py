"""Calibration state, revision, and review persistence behind the Storage facade."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _CalibrationStorageMixin:
    def preview_landmark_for_match(self, match_id: str) -> dict:
        from .workbench.cache import REBUILD_FOR
        from .workbench.geometry import preview_landmark_fit

        match = self.get_match(match_id)
        revision = self.calibration_revision(match_id)
        if revision is not None and revision.accepted:
            evaluation = dict(revision.evaluation)
            return {
                "preview": False,
                "profile": dict(revision.profile),
                "committed": True,
                "certified": False,
                "accepted": bool(evaluation.get("accepted", True)),
                "measured": True,
                "visionRerun": False,
                "residualP95M": evaluation.get("p95M", revision.profile.get("residualP95M")),
                "rebuild": list(REBUILD_FOR["calibration"]),
                "reasonCodes": [],
            }
        preview = preview_landmark_fit(residual_p95_m=float("inf"), max_p95_m=3.0)
        preview["residualP95M"] = None
        preview["measured"] = False
        preview["accepted"] = False
        preview["certified"] = False
        preview["rebuild"] = list(REBUILD_FOR["calibration"])
        preview["reasonCodes"] = ["LANDMARK_RESIDUAL_UNMEASURED"]
        preview["committed"] = False
        return preview

    def commit_calibration_for_match(self, match_id: str, payload: dict) -> dict:
        from .workbench.geometry import CalibrationProfile, commit_calibration
        from .workbench.review import correction_api_payload

        match = self.get_match(match_id)
        controls = {key: payload[key] for key in ("expectedVersion", "baseGeneration", "commandId", "idempotencyKey") if key in payload}
        profile = CalibrationProfile.model_validate({key: value for key, value in payload.items() if key not in controls})
        result = commit_calibration(profile)
        if result.get("committed"):
            try:
                self.current_generation(match_id)
            except FileNotFoundError:
                revision = self._new_calibration_revision(
                    match_id,
                    profile=result["profile"],
                    evaluation={**dict(result["evaluation"]), "measured": True},
                )
                self._save_calibration_revision(match_id, revision)
            else:
                saved = self.submit_correction(
                    match_id,
                    kind="calibration",
                    expected_version=controls.get("expectedVersion"),
                    base_generation=controls.get("baseGeneration"),
                    command_id=controls.get("commandId"),
                    idempotency_key=controls.get("idempotencyKey"),
                    payload={"profile": profile.model_dump(mode="json")},
                )
                result["correction"] = correction_api_payload(saved)
                result["committed"] = saved.applyState == "applied"
                result["generationId"] = saved.appliedGeneration
        return result

    def calibration_for_match(self, match_id: str, payload: dict | None = None) -> dict:
        from .workbench.geometry import (
            Landmark,
            evaluate_landmarks,
            from_legacy_four_points,
            validate_fit_points,
            withhold_if_invalid,
        )
        from .workbench.review import correction_api_payload

        match = self.get_match(match_id)
        points = [{"x": float(point.x), "y": float(point.y)} for point in match.config.manualHomographyPoints]
        if len(points) != 4:
            return {
                "availability": "calibration_unavailable",
                "reasonCodes": ["MANUAL_POINTS_MISSING"],
                "committed": False,
                "measured": False,
                "visionRerun": False,
                "correction": None,
            }
        try:
            source_clock = self.load_analysis_artifact(match_id, "source_clock")
        except FileNotFoundError:
            source_clock = {}
        point_errors = validate_fit_points(
            points,
            width=source_clock.get("width") if isinstance(source_clock, dict) else None,
            height=source_clock.get("height") if isinstance(source_clock, dict) else None,
        )
        if point_errors:
            return {
                "availability": "calibration_unavailable",
                "reasonCodes": point_errors,
                "committed": False,
                "measured": False,
                "visionRerun": False,
                "correction": None,
            }
        profile = from_legacy_four_points(
            points,
            calibration_id=match_id,
            pitch_length_m=match.config.pitchLengthM or 105.0,
            pitch_width_m=match.config.pitchWidthM or 68.0,
        )
        body = dict(payload or {})
        holdout: list = []
        for item in body.get("landmarks") or []:
            if not isinstance(item, dict) or item.get("independentHoldout") is not True:
                continue
            holdout.append(
                Landmark(
                    name=str(item.get("name") or f"holdout_{len(holdout)}"),
                    imageX=float(item.get("imageX") or 0.0),
                    imageY=float(item.get("imageY") or 0.0),
                    pitchX=float(item.get("pitchX") or 0.0),
                    pitchY=float(item.get("pitchY") or 0.0),
                    independentHoldout=True,
                )
            )
        stored = self._load_calibration_evaluation(match_id)
        previous_revision = self.calibration_revision(match_id)
        committed = False
        correction = None
        measured = False
        residual = None
        if holdout:
            profile = profile.model_copy(update={"landmarks": list(profile.landmarks) + holdout})
            measured_evaluation = evaluate_landmarks(profile, max_p95_m=3.0)
            evaluation = measured_evaluation
            measured = True
            residual = measured_evaluation.get("p95M")
            if measured_evaluation.get("accepted"):
                revision = self._new_calibration_revision(
                    match_id,
                    profile=profile.model_dump(mode="json"),
                    evaluation={**measured_evaluation, "measured": True},
                )
                saved = self.submit_correction(
                    match_id,
                    kind="calibration",
                    payload={
                        "revision": revision,
                        "previousRevision": (
                            None
                            if previous_revision is None
                            else previous_revision.model_dump(mode="json")
                        ),
                    },
                    author=str(body.get("author") or "analyst"),
                    crash_before_commit=bool(body.get("crashBeforeCommit")),
                )
                correction = correction_api_payload(saved)
                committed = saved.applyState == "applied"
                if committed:
                    stored = {**measured_evaluation, "measured": True}
                else:
                    evaluation = {
                        "accepted": False,
                        "reasonCodes": ["CALIBRATION_UNAVAILABLE"],
                        "holdoutCount": len(holdout),
                    }
                    measured = False
                    residual = None
            else:
                committed = False
        elif stored:
            evaluation = {
                "accepted": bool(stored.get("accepted")),
                "p95M": stored.get("p95M"),
                "holdoutCount": stored.get("holdoutCount") or 0,
                "farSideMaxM": stored.get("farSideMaxM"),
                "reasonCodes": list(stored.get("reasonCodes") or []),
            }
            measured = stored.get("measured") is True
            residual = stored.get("p95M") if measured else None
        else:
            evaluation = evaluate_landmarks(profile, max_p95_m=3.0)
        withheld = withhold_if_invalid(profile, "team_width_m")
        if not holdout and stored.get("accepted") and stored.get("measured") is True:
            withheld = {"metric": "team_width_m", "availability": "available", "reasonCodes": [], "value": "computed"}
        elif evaluation.get("accepted") is not True:
            withheld = {"metric": "team_width_m", "availability": "withheld", "reasonCodes": list(evaluation.get("reasonCodes") or ["CALIBRATION_UNAVAILABLE"]), "value": None}
        return {
            **profile.model_dump(mode="json"),
            "evaluation": evaluation,
            "withheld": withheld,
            "fromStoredPoints": True,
            "measured": measured,
            "residualP95M": residual,
            "committed": committed,
            "visionRerun": False,
            "correction": correction,
        }

    def _load_calibration_evaluation(self, match_id: str) -> dict:
        revision = self.calibration_revision(match_id)
        if revision is not None:
            return dict(revision.evaluation)
        try:
            payload = self.load_analysis_artifact(match_id, "calibration_evaluation")
        except FileNotFoundError:
            return {}
        return dict(payload) if isinstance(payload, dict) else {}

    def _save_calibration_evaluation(self, match_id: str, evaluation: dict) -> None:
        if not evaluation:
            path = self._match_dir(match_id) / "calibration_evaluation.json"
            if path.exists():
                path.unlink()
            return
        self.save_analysis_artifact(match_id, "calibration_evaluation", evaluation)

    def _restore_calibration_evaluation(self, match_id: str, previous: dict) -> None:
        self._save_calibration_evaluation(match_id, previous)

    def calibration_revision(self, match_id: str):
        from .generations import _UNSET
        from .workbench.contracts import CalibrationRevision
        value = self.generations.calibration(match_id)
        if value is not _UNSET:
            return None if value is None else CalibrationRevision.model_validate(value)
        return self._legacy_calibration_revision(match_id)

    def _legacy_calibration_revision(self, match_id: str):
        from .workbench.contracts import CalibrationRevision

        try:
            return CalibrationRevision.model_validate(
                self.load_analysis_artifact(match_id, "calibration_revision")
            )
        except FileNotFoundError:
            pass
        try:
            legacy_profile = self.load_analysis_artifact(match_id, "calibration_profile")
        except FileNotFoundError:
            legacy_profile = {}
        try:
            legacy_evaluation = self.load_analysis_artifact(match_id, "calibration_evaluation")
        except FileNotFoundError:
            legacy_evaluation = {}
        if not legacy_profile and not legacy_evaluation:
            return None
        profile = dict(legacy_profile.get("profile") or legacy_profile)
        evaluation = dict(legacy_evaluation or legacy_profile.get("evaluation") or {})
        match = self.get_match(match_id)
        accepted = bool(evaluation.get("accepted")) and evaluation.get("measured") is True
        digest = hashlib.sha256(
            json.dumps(
                {"profile": profile, "evaluation": evaluation, "source": self.source_sha256(match_id)},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        return CalibrationRevision(
            revisionId=f"cal_{digest[:16]}",
            profile=profile,
            evaluation=evaluation,
            accepted=accepted,
            measured=evaluation.get("measured") is True,
            sourceSha256=self.source_sha256(match_id),
            validInterval={"start": 0.0, "end": None},
            createdAt=_utcnow().isoformat(),
            pitchLengthM=float(profile.get("pitchLengthM") or match.config.pitchLengthM or 105.0),
            pitchWidthM=float(profile.get("pitchWidthM") or match.config.pitchWidthM or 68.0),
            migrated=True,
        )

    def _save_calibration_revision(self, match_id: str, revision: dict) -> None:
        from .workbench.contracts import CalibrationRevision

        canonical = CalibrationRevision.model_validate(revision)
        self.save_analysis_artifact(match_id, "calibration_revision", canonical.model_dump(mode="json"))

    def _new_calibration_revision(self, match_id: str, *, profile: dict, evaluation: dict) -> dict:
        match = self.get_match(match_id)
        source_sha = self.source_sha256(match_id)
        identity = hashlib.sha256(
            json.dumps(
                {"profile": profile, "evaluation": evaluation, "source": source_sha},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        return {
            "revisionId": f"cal_{identity[:16]}",
            "profile": profile,
            "evaluation": evaluation,
            "accepted": bool(evaluation.get("accepted")) and evaluation.get("measured") is True,
            "measured": evaluation.get("measured") is True,
            "sourceSha256": source_sha,
            "validInterval": {"start": profile.get("sourceIntervalStart", 0.0), "end": profile.get("sourceIntervalEnd")},
            "createdAt": _utcnow().isoformat(),
            "fitPointSpace": "source_pixels",
            "pitchLengthM": float(profile.get("pitchLengthM") or match.config.pitchLengthM or 105.0),
            "pitchWidthM": float(profile.get("pitchWidthM") or match.config.pitchWidthM or 68.0),
            "migrated": False,
        }

    def _restore_calibration_revision(self, match_id: str, revision: dict | None) -> None:
        path = self._match_dir(match_id) / "calibration_revision.json"
        if revision is None:
            path.unlink(missing_ok=True)
            return
        self._save_calibration_revision(match_id, revision)
