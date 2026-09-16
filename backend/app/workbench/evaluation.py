"""GA-13 frozen evaluation scaffolding. Never invent independent labels."""

from __future__ import annotations


from .contracts import StrictModel

PROTOCOL_VERSION = "football_analysis_pilot_labels_v3"
FROZEN_TASK_COUNT = 18
FROZEN_SAMPLED_FRAMES = 9297
REQUIRED_MINUTES = 30.0


class EvaluationGate(StrictModel):
    protocolVersion: str
    completeTasks: int
    requiredTasks: int
    completeMinutes: float
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


def current_repository_evaluation_gate() -> EvaluationGate:
    """Authoritative current-state gate: independent labels remain incomplete."""

    return evaluate_protocol_prerequisites(
        complete_tasks=0,
        complete_minutes=0.0,
        locked_labels_present=False,
        native_predictions_present=False,
        team_declarations_present=False,
        scorer_replayable=True,
    )


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
) -> dict[str, object]:
    reasons: list[str] = []
    if label_space != "image_space":
        reasons.append("INCOMPATIBLE_HOTA_LABEL_SPACE")
    if hand_edited_summary:
        reasons.append("HANDEDITED_SUMMARY_IS_NOT_A_RESULT")
    if not native_predictions_present:
        reasons.append("NATIVE_PREDICTIONS_REQUIRED")
    return {
        "scored": not reasons,
        "hota": None,
        "idf1": None,
        "trackevalIsGroundTruth": False,
        "reasonCodes": reasons,
    }
