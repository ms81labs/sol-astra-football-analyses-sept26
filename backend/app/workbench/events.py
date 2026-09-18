"""GA-09 candidate events as intervals with a frozen matching scorer."""

from __future__ import annotations

import hashlib
from typing import Any, Literal

from pydantic import Field

from .contracts import StrictModel
from .jobs import DurableJobLedger

FROZEN_EVENT_TOLERANCE_SECONDS = 0.5
EVENT_FAMILIES = ("pass", "turnover", "recovery", "shot", "carry", "press")


class FootballEvent(StrictModel):
    family: str
    status: Literal["candidate", "accepted", "rejected", "withheld"]
    intervalStart: float
    intervalEnd: float
    anchorTime: float | None = None
    timingUncertainty: float | None = 0.2
    accepted: bool = False
    reasonCodes: list[str] = Field(default_factory=list)
    playerAttribution: str | None = None


class ClassScore(StrictModel):
    precision: float = 0.0
    recall: float = 0.0
    boundaryErrors: int = 0
    falsePositives: int = 0
    falseNegatives: int = 0


class EventScoreReceipt(StrictModel):
    byClass: dict[str, ClassScore]
    toleranceSeconds: float = FROZEN_EVENT_TOLERANCE_SECONDS
    labelsIndependent: bool
    notes: str = "Heuristic events remain provisional until independent labels exist."


def propose_event(
    *,
    family: str,
    release: dict[str, Any] | None,
    receipt: dict[str, Any] | None,
) -> FootballEvent:
    if family == "pass" and (release is None or receipt is None):
        return FootballEvent(
            family=family,
            status="withheld",
            intervalStart=float((release or {}).get("time") or 0.0),
            intervalEnd=float((receipt or {}).get("time") or 0.0),
            accepted=False,
            reasonCodes=["MISSING_RELEASE_OR_RECEIPT"],
        )
    start = float((release or {}).get("time") or 0.0)
    end = float((receipt or {}).get("time") or start)
    return FootballEvent(
        family=family,
        status="candidate",
        intervalStart=start,
        intervalEnd=end,
        anchorTime=start,
        timingUncertainty=0.2,
        accepted=False,
        reasonCodes=["PROVISIONAL_EVENT_SUGGESTION"],
        playerAttribution=None if family == "turnover" else str((release or {}).get("playerId") or "") or None,
    )


def score_events(
    *,
    predictions: list[dict[str, Any]],
    labels: list[dict[str, Any]],
    labels_independent: bool,
    tolerance_seconds: float = FROZEN_EVENT_TOLERANCE_SECONDS,
) -> EventScoreReceipt:
    families = sorted({str(item.get("family")) for item in predictions + labels if item.get("family")})
    by_class: dict[str, ClassScore] = {}
    for family in families:
        pred = [item for item in predictions if item.get("family") == family]
        truth = [item for item in labels if item.get("family") == family]
        matched = 0
        boundary = 0
        used: set[int] = set()
        for candidate in pred:
            hit = None
            for index, label in enumerate(truth):
                if index in used:
                    continue
                if abs(float(candidate.get("intervalStart") or 0.0) - float(label.get("intervalStart") or 0.0)) <= tolerance_seconds:
                    hit = (index, label)
                    break
            if hit is None:
                continue
            used.add(hit[0])
            matched += 1
            if abs(float(candidate.get("intervalEnd") or 0.0) - float(hit[1].get("intervalEnd") or 0.0)) > tolerance_seconds:
                boundary += 1
        false_pos = max(0, len(pred) - matched)
        false_neg = max(0, len(truth) - matched)
        precision = matched / len(pred) if pred else 0.0
        recall = matched / len(truth) if truth else 0.0
        by_class[family] = ClassScore(
            precision=precision,
            recall=recall,
            boundaryErrors=boundary,
            falsePositives=false_pos,
            falseNegatives=false_neg,
        )
    return EventScoreReceipt(byClass=by_class, toleranceSeconds=tolerance_seconds, labelsIndependent=labels_independent)


def ownership_invalidation() -> list[str]:
    return DurableJobLedger().invalidate_for("track_edit")


def learned_temporal(*, labelled_errors_justify: bool) -> dict[str, bool]:
    return {
        "enabled": labelled_errors_justify,
        "replacesStateMachine": False,
        "automaticPublication": False,
    }


def partition_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = [item for item in events if item.get("reviewStatus") == "accepted"]
    retained = [item for item in events if item.get("reviewStatus") == "rejected"]
    return {
        "acceptedViews": accepted,
        "retainedCandidates": retained,
        "rejectedRemovedFromAcceptedViews": True,
    }


def event_review_status(kind: str) -> str | None:
    if kind == "event_accept":
        return "accepted"
    if kind == "event_reject":
        return "rejected"
    return None


def with_stable_event_id(event: Any):
    primary_track = event.fromTrackId if event.fromTrackId is not None else event.toTrackId
    identity = "|".join(
        (event.type, str(event.team or ""), f"{round(event.timestamp, 1):.1f}", str(primary_track or ""))
    )
    return event.model_copy(update={"eventId": f"ev_{hashlib.sha1(identity.encode()).hexdigest()[:16]}"})


def event_matches_review_payload(event: Any, payload: dict[str, Any], *, match_id: str, index: int) -> bool:
    event_id = payload.get("eventId") or payload.get("id")
    frame = payload.get("frame") if payload.get("frame") is not None else payload.get("frameId")
    event_type = payload.get("type")
    frame_id = int(getattr(event, "frameId", 0) or 0)
    event_kind = str(getattr(event, "type", "") or "")
    timestamp = getattr(event, "timestamp", None)
    synthetic_id = f"{match_id}:{index}"
    evidence_id = f"event:{frame_id}:{event_kind}:{timestamp}"
    stable_id = getattr(event, "eventId", None)
    if event_id not in {None, ""}:
        if str(event_id) not in {synthetic_id, evidence_id, str(frame_id), stable_id}:
            return False
    elif frame is not None:
        if frame_id != int(frame):
            return False
    else:
        return False
    if event_type not in {None, ""} and event_kind != str(event_type):
        return False
    return True


def apply_event_review(
    events: list[Any],
    *,
    kind: str,
    payload: dict[str, Any],
    match_id: str,
) -> tuple[list[Any], list[dict[str, Any]]]:
    status = event_review_status(kind)
    if status is None:
        return events, []
    previous: list[dict[str, Any]] = []
    updated: list[Any] = []
    for index, event in enumerate(events):
        if not event_matches_review_payload(event, payload, match_id=match_id, index=index):
            updated.append(event)
            continue
        previous.append(
            {
                "frameId": int(getattr(event, "frameId", 0) or 0),
                "timestamp": getattr(event, "timestamp", None),
                "type": getattr(event, "type", None),
                "reviewStatus": getattr(event, "reviewStatus", "unreviewed"),
            }
        )
        updated.append(event.model_copy(update={"reviewStatus": status}))
    return updated, previous


def restore_event_review(events: list[Any], previous: list[dict[str, Any]]) -> list[Any]:
    restored: list[Any] = []
    remaining = [dict(item) for item in previous]
    for event in events:
        match_index = next(
            (
                index
                for index, item in enumerate(remaining)
                if int(item.get("frameId") or 0) == int(getattr(event, "frameId", 0) or 0)
                and item.get("type") == getattr(event, "type", None)
                and item.get("timestamp") == getattr(event, "timestamp", None)
            ),
            None,
        )
        if match_index is None:
            restored.append(event)
            continue
        snapshot = remaining.pop(match_index)
        restored.append(event.model_copy(update={"reviewStatus": snapshot.get("reviewStatus") or "unreviewed"}))
    return restored
