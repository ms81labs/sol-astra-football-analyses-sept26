"""GA-10 typed tactical search and GA-11 optional assistance routing."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import Field

from backend.app.ai_policy import ground_output

from .contracts import StrictModel

ALLOWED_EVENT_FAMILIES = frozenset(
    {
        "pass",
        "progressive_pass",
        "through_ball",
        "cross",
        "shot",
        "goal",
        "turnover",
        "recovery",
        "tackle",
        "interception",
        "carry",
        "box_entry",
        "final_third_entry",
    }
)
ALLOWED_TEAMS = frozenset({"my_team", "enemy"})


class TypedQuery(StrictModel):
    team: Literal["my_team", "enemy"] | None = None
    period: int | None = None
    eventFamily: str
    successorEvent: str | None = None
    maxGapSeconds: float | None = None
    unanswerable: bool = False
    reason: str | None = None


class SearchHit(StrictModel):
    eventId: str
    matchId: str
    timestamp: float
    evidenceIds: list[str] = Field(default_factory=list)
    label: str


class AssistancePolicy(StrictModel):
    taskType: str
    maxCalls: int = 1
    maxRepairAttempts: int = 1
    spendCap: float = 0.0
    allowedModelIds: list[str] = Field(default_factory=list)
    timeoutSeconds: float = 30.0
    cloudPermitted: bool = False


class AssistanceDisposition(StrictModel):
    route: Literal["template", "local", "cloud", "rejected"]
    reasonCodes: list[str] = Field(default_factory=list)
    callsUsed: int = 0
    spend: float = 0.0
    output: dict[str, Any] = Field(default_factory=dict)


_QUERY_RE = re.compile(
    r"(?:(?P<team>our|my team|enemy|opponent) )?"
    r"(?:(?P<period>first-half|second-half|period\s+(?P<period_n>\d+)) )?"
    r"(?P<event>turnovers|turnover|shots|shot|passes|pass|recoveries|recovery)"
    r"(?: followed by (?:a )?(?P<successor>shot|pass|turnover)(?: within (?P<gap>\d+|ten) seconds)?)?",
    re.IGNORECASE,
)


def parse_typed_query(text: str) -> TypedQuery:
    stripped = text.strip()
    if not stripped:
        return TypedQuery(eventFamily="pass", unanswerable=True, reason="empty_query")
    lowered = stripped.lower()
    if any(token in lowered for token in ("sql", "select ", "drop table", "import os", "__import__", "eval(")):
        return TypedQuery(eventFamily="pass", unanswerable=True, reason="refused_code_execution")
    match = _QUERY_RE.search(stripped)
    if match is None:
        return TypedQuery(eventFamily="pass", unanswerable=True, reason="unrecognised_query")
    event = _canonical_event(match.group("event"))
    successor = _canonical_event(match.group("successor")) if match.group("successor") else None
    team_token = (match.group("team") or "").lower()
    team = "enemy" if team_token in {"enemy", "opponent"} else ("my_team" if team_token else None)
    period = None
    if match.group("period_n"):
        period = int(match.group("period_n"))
    elif match.group("period"):
        period = 1 if "first" in match.group("period").lower() else 2
    gap_token = match.group("gap")
    gap = 10.0 if gap_token == "ten" else (float(gap_token) if gap_token else None)
    if event not in ALLOWED_EVENT_FAMILIES:
        return TypedQuery(eventFamily=event, unanswerable=True, reason="unknown_event_family")
    if successor and successor not in ALLOWED_EVENT_FAMILIES:
        return TypedQuery(eventFamily=event, unanswerable=True, reason="unknown_successor")
    return TypedQuery(
        team=team,
        period=period,
        eventFamily=event,
        successorEvent=successor,
        maxGapSeconds=gap,
    )


def execute_typed_query(events: list[dict[str, Any]], query: TypedQuery, *, match_id: str) -> list[SearchHit]:
    if query.unanswerable:
        return []
    hits: list[SearchHit] = []
    ordered = sorted(events, key=lambda item: float(item.get("timestamp") or 0.0))
    for index, event in enumerate(ordered):
        if str(event.get("type")) != query.eventFamily:
            continue
        if query.team and event.get("team") not in {query.team, None}:
            continue
        if query.period is not None and int(event.get("period") or 0) not in {0, query.period}:
            continue
        if query.successorEvent:
            successor = _find_successor(ordered, index, query.successorEvent, query.maxGapSeconds)
            if successor is None:
                continue
        hits.append(
            SearchHit(
                eventId=str(event.get("id") or f"{match_id}:{index}"),
                matchId=match_id,
                timestamp=float(event.get("timestamp") or 0.0),
                evidenceIds=list(event.get("evidenceIds") or []),
                label=str(event.get("type")),
            )
        )
    return hits


def _find_successor(
    events: list[dict[str, Any]],
    index: int,
    successor: str,
    max_gap: float | None,
) -> dict[str, Any] | None:
    start = float(events[index].get("timestamp") or 0.0)
    for candidate in events[index + 1 :]:
        stamp = float(candidate.get("timestamp") or 0.0)
        if max_gap is not None and stamp - start > max_gap:
            return None
        if str(candidate.get("type")) == successor:
            return candidate
    return None


def _canonical_event(token: str) -> str:
    mapping = {
        "turnovers": "turnover",
        "turnover": "turnover",
        "shots": "shot",
        "shot": "shot",
        "passes": "pass",
        "pass": "pass",
        "recoveries": "recovery",
        "recovery": "recovery",
    }
    return mapping.get(token.lower(), token.lower())


def template_report(metrics: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, Any]:
    available = [metric for metric in metrics if metric.get("availability") == "available"]
    unknown = [metric for metric in metrics if metric.get("availability") != "available"]
    return {
        "kind": "deterministic_template",
        "availableMetrics": available,
        "unknownMetrics": unknown,
        "eventCount": len(events),
        "limitations": [metric.get("reasonCodes") for metric in unknown],
    }


class AssistanceRouter:
    def __init__(self, *, providers_enabled: bool = False) -> None:
        self.providers_enabled = providers_enabled
        self.calls = 0
        self.spend = 0.0

    def run(
        self,
        *,
        policy: AssistancePolicy,
        metrics: list[dict[str, Any]],
        events: list[dict[str, Any]],
        claimed_evidence_ids: list[str] | None = None,
        known_evidence_ids: set[str] | None = None,
    ) -> AssistanceDisposition:
        known = known_evidence_ids or set()
        claimed = claimed_evidence_ids or []
        grounded = ground_output({"evidence": claimed}, known_ids=known) if claimed else None
        if grounded and grounded["route"] == "rejected":
            return AssistanceDisposition(
                route="rejected",
                reasonCodes=list(grounded["reasonCodes"]),
                output=grounded["output"],
            )
        if not self.providers_enabled or not policy.allowedModelIds or policy.spendCap <= 0:
            return AssistanceDisposition(
                route="template",
                reasonCodes=["PROVIDER_DISABLED"],
                output=template_report(metrics, events),
            )
        if self.calls >= policy.maxCalls or self.spend >= policy.spendCap:
            return AssistanceDisposition(
                route="template",
                reasonCodes=["PROVIDER_DISABLED"],
                callsUsed=self.calls,
                spend=self.spend,
                output=template_report(metrics, events),
            )
        self.calls += 1
        return AssistanceDisposition(
            route="local" if not policy.cloudPermitted else "cloud",
            callsUsed=self.calls,
            spend=self.spend,
            output={"status": "provider_stub"},
        )
