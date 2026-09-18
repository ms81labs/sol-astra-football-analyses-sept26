"""GA-13 frozen evaluation scaffolding. Never invent independent labels."""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
from typing import Literal

from .contracts import StrictModel

PROTOCOL_VERSION = "football_analysis_pilot_labels_v3"
FROZEN_TASK_COUNT = 18
FROZEN_SAMPLED_FRAMES = 9297
REQUIRED_MINUTES = 30.0
EvaluationStatus = Literal["unknown", "prerequisites_unmet", "prerequisites_ok", "executed", "scored"]


class EvaluationGate(StrictModel):
    status: EvaluationStatus
    protocolVersion: str
    completeTasks: int | None
    requiredTasks: int
    completeMinutes: float | None
    requiredMinutes: float
    lockedLabelsPresent: bool
    nativePredictionsPresent: bool
    teamDeclarationsPresent: bool
    replayable: bool
    accepted: bool
    reasonCodes: list[str]


def evaluate_protocol_prerequisites(
    *,
    complete_tasks: int,
    complete_minutes: float,
    locked_labels_present: bool,
    native_predictions_present: bool,
    team_declarations_present: bool,
    scorer_replayable: bool,
) -> EvaluationGate:
    reasons: list[str] = []
    if complete_tasks < FROZEN_TASK_COUNT:
        reasons.append("LABELS_INCOMPLETE")
    if complete_minutes < REQUIRED_MINUTES:
        reasons.append("LABELS_INCOMPLETE")
    if not locked_labels_present:
        reasons.append("LABELS_INCOMPLETE")
    if not native_predictions_present:
        reasons.append("LABELS_INCOMPLETE")
    if not team_declarations_present:
        reasons.append("LABELS_INCOMPLETE")
    if not scorer_replayable:
        reasons.append("LABELS_INCOMPLETE")
    accepted = not reasons
    return EvaluationGate(
        status="prerequisites_ok" if accepted else "prerequisites_unmet",
        protocolVersion=PROTOCOL_VERSION,
        completeTasks=complete_tasks,
        requiredTasks=FROZEN_TASK_COUNT,
        completeMinutes=complete_minutes,
        requiredMinutes=REQUIRED_MINUTES,
        lockedLabelsPresent=locked_labels_present,
        nativePredictionsPresent=native_predictions_present,
        teamDeclarationsPresent=team_declarations_present,
        replayable=scorer_replayable,
        accepted=accepted,
        reasonCodes=reasons,
    )


def current_repository_evaluation_gate(*, manifest_path: Path | None = None) -> EvaluationGate:
    path = manifest_path or Path(__file__).parents[2] / "evaluation" / "manifest.json"
    if not path.is_file():
        return EvaluationGate(
            status="unknown",
            protocolVersion=PROTOCOL_VERSION,
            completeTasks=None,
            requiredTasks=FROZEN_TASK_COUNT,
            completeMinutes=None,
            requiredMinutes=REQUIRED_MINUTES,
            lockedLabelsPresent=False,
            nativePredictionsPresent=False,
            teamDeclarationsPresent=False,
            replayable=False,
            accepted=False,
            reasonCodes=["EVALUATION_MANIFEST_MISSING"],
        )
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("schemaVersion") != 1:
            raise ValueError("unsupported evaluation manifest version")
        artifacts = {
            str(item.get("kind")): str(item.get("sha256"))
            for item in manifest.get("artifacts", [])
            if isinstance(item, dict)
        }
        prediction_digest = artifacts.get("predictions") or artifacts.get("prediction")
        label_digest = artifacts.get("labels") or artifacts.get("label")
        result = dict(manifest.get("results") or {})
        score = score_hota_idf1(
            label_space="image_space",
            hand_edited_summary=False,
            native_predictions_present=bool(manifest.get("nativePredictionsPresent")),
            scorer_executed=bool(result),
            hota=result.get("hota"),
            idf1=result.get("idf1"),
            prediction_digest=prediction_digest,
            label_digest=label_digest,
            scorer_version=manifest.get("scorerVersion"),
            source_identity=manifest.get("sourceIdentity"),
        )
        prerequisites = evaluate_protocol_prerequisites(
            complete_tasks=int(manifest.get("completeTasks", 0)),
            complete_minutes=float(manifest.get("completeMinutes", 0.0)),
            locked_labels_present=bool(manifest.get("lockedLabelsPresent")),
            native_predictions_present=bool(manifest.get("nativePredictionsPresent")),
            team_declarations_present=bool(manifest.get("teamDeclarationsPresent")),
            scorer_replayable=bool(manifest.get("scorerReplayable")),
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return EvaluationGate(
            status="unknown",
            protocolVersion=PROTOCOL_VERSION,
            completeTasks=None,
            requiredTasks=FROZEN_TASK_COUNT,
            completeMinutes=None,
            requiredMinutes=REQUIRED_MINUTES,
            lockedLabelsPresent=False,
            nativePredictionsPresent=False,
            teamDeclarationsPresent=False,
            replayable=False,
            accepted=False,
            reasonCodes=["EVALUATION_MANIFEST_INVALID"],
        )
    status: EvaluationStatus = prerequisites.status
    reasons = list(prerequisites.reasonCodes)
    if prerequisites.status == "prerequisites_ok":
        status = score["status"]  # type: ignore[assignment]
        reasons.extend(str(reason) for reason in score["reasonCodes"])
    return prerequisites.model_copy(update={"status": status, "accepted": status == "scored", "reasonCodes": reasons})


def evaluation_measures() -> dict[str, object]:
    return {
        "hotaIdf1RequiresCompatibleImageSpaceLabels": True,
        "officialPitchPositionsAreNotHotaLabels": True,
        "trackevalIsGroundTruth": False,
        "annotationServiceHealthSatisfiesLabelGate": False,
        "pooledAverageOnly": False,
        "handEditedSummaryIsResult": False,
        "analystWorkflow": analyst_workflow_measures(),
    }


def analyst_workflow_measures() -> dict[str, object]:
    return {
        "measured": False,
        "analystCompletedReviewedMatch": False,
        "correctionTimeSeconds": None,
        "missedUsefulPassages": None,
        "exportUsefulness": None,
        "trust": None,
        "developerIntervention": None,
        "reasonCodes": ["ANALYST_ACCEPTANCE_MISSING"],
    }


def score_hota_idf1(
    *,
    label_space: str,
    hand_edited_summary: bool,
    native_predictions_present: bool,
    scorer_executed: bool = False,
    hota: float | None = None,
    idf1: float | None = None,
    prediction_digest: str | None = None,
    label_digest: str | None = None,
    scorer_version: str | None = None,
    source_identity: str | None = None,
) -> dict[str, object]:
    reasons: list[str] = []
    if label_space != "image_space":
        reasons.append("INCOMPATIBLE_HOTA_LABEL_SPACE")
    if hand_edited_summary:
        reasons.append("HANDEDITED_SUMMARY_IS_NOT_A_RESULT")
    if not native_predictions_present:
        reasons.append("NATIVE_PREDICTIONS_REQUIRED")
    status: EvaluationStatus = "prerequisites_unmet" if reasons else "prerequisites_ok"
    if not reasons and scorer_executed:
        status = "executed"
        numeric_results = all(
            isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
            for value in (hota, idf1)
        )
        if not numeric_results:
            reasons.append("EVALUATION_RESULT_NOT_RECORDED")
            hota = idf1 = None
        valid_digests = all(
            isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None
            for value in (prediction_digest, label_digest)
        )
        if not valid_digests or not all(
            isinstance(value, str) and value.strip() for value in (scorer_version, source_identity)
        ):
            reasons.append("EVALUATION_PROVENANCE_INCOMPLETE")
        if not reasons:
            status = "scored"
    return {
        "status": status,
        "scored": status == "scored",
        "hota": hota,
        "idf1": idf1,
        "predictionDigest": prediction_digest,
        "labelDigest": label_digest,
        "scorerVersion": scorer_version,
        "sourceIdentity": source_identity,
        "trackevalIsGroundTruth": False,
        "reasonCodes": reasons,
    }
