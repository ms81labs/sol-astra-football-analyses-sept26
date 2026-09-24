"""GA-10 typed tactical search and GA-11 optional assistance routing."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import Field, model_validator

from backend.app.ai_policy import ground_output
from backend.app.provider_gateway import ApprovedEvidencePackage, validate_output

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


class SuccessorConstraint(StrictModel):
    kind: str
    team: Literal["same", "opponent", "my_team", "enemy"] | None = None
    period: int | None = Field(default=None, ge=1, le=4)
    withinSeconds: float | None = Field(default=None, gt=0, le=600, allow_inf_nan=False)


class TypedQuery(StrictModel):
    team: Literal["my_team", "enemy"] | None = None
    period: int | None = Field(default=None, ge=1, le=4)
    eventFamily: str
    playerTrackId: int | None = Field(default=None, ge=0, le=1_000_000)
    reviewStatus: Literal["accepted", "unreviewed"] | None = None
    successor: SuccessorConstraint | None = None
    timeStartSeconds: float | None = Field(default=None, ge=0, le=86_400, allow_inf_nan=False)
    timeEndSeconds: float | None = Field(default=None, ge=0, le=86_400, allow_inf_nan=False)
    includeUnknown: bool = False
    interpreted: dict[str, Any] = Field(default_factory=dict)
    unsupportedTerms: list[str] = Field(default_factory=list)
    unanswerable: bool = False
    reason: str | None = None

    @model_validator(mode="after")
    def supported_predicates(self) -> "TypedQuery":
        if self.eventFamily not in ALLOWED_EVENT_FAMILIES \
                or (self.successor and self.successor.kind not in ALLOWED_EVENT_FAMILIES) \
                or (self.timeStartSeconds is not None and self.timeEndSeconds is not None
                    and self.timeStartSeconds > self.timeEndSeconds):
            raise ValueError("unsupported or invalid typed query predicate")
        return self

    @property
    def successorEvent(self) -> str | None:
        return self.successor.kind if self.successor else None

    @property
    def maxGapSeconds(self) -> float | None:
        return self.successor.withinSeconds if self.successor else None


class SearchHit(StrictModel):
    eventId: str
    matchId: str
    timestamp: float
    frameId: int | None = None
    intervalStart: float | None = None
    intervalEnd: float | None = None
    reviewStatus: str | None = None
    evidenceIds: list[str] = Field(default_factory=list)
    label: str


class AssistancePolicy(StrictModel):
    taskType: str
    maxCalls: int = 1
    maxRepairAttempts: int = 1
    spendCap: float = 0.0
    reservedCallCost: float = 0.0
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
    r"(?:(?P<review>accepted|unreviewed) )?"
    r"(?P<event>turnovers|turnover|shots|shot|passes|pass|recoveries|recovery)"
    r"(?: followed by (?:a )?(?:(?P<successor_team>our|my team|enemy|opponent|same) )?"
    r"(?P<successor>shots|shot|passes|pass|turnovers|turnover)(?: within (?P<gap>\d+|ten) seconds)?)?",
    re.IGNORECASE,
)


def parse_typed_query(text: str, *, include_unknown: bool = False) -> TypedQuery:
    stripped = text.strip()
    if len(stripped) > 512:
        return TypedQuery(eventFamily="pass", unanswerable=True, reason="query_too_long")
    if not stripped:
        return TypedQuery(eventFamily="pass", unanswerable=True, reason="empty_query")
    lowered = stripped.lower()
    if any(token in lowered for token in ("sql", "select ", "drop table", "import os", "__import__", "eval(")):
        return TypedQuery(eventFamily="pass", unanswerable=True, reason="refused_code_execution")
    match = _QUERY_RE.search(stripped)
    if match is None:
        return TypedQuery(
            eventFamily="pass",
            unsupportedTerms=[token.lower() for token in re.findall(r"[A-Za-z0-9_'-]+", stripped)],
            unanswerable=True,
            reason="unrecognised_query",
        )
    event = _canonical_event(match.group("event"))
    successor = _canonical_event(match.group("successor")) if match.group("successor") else None
    team_token = (match.group("team") or "").lower()
    team = "enemy" if team_token in {"enemy", "opponent"} else ("my_team" if team_token else None)
    period = None
    if match.group("period_n"):
        period = int(match.group("period_n"))
    elif match.group("period"):
        period = 1 if "first" in match.group("period").lower() else 2
    if period is not None and not 1 <= period <= 4:
        return TypedQuery(eventFamily=event, unanswerable=True, reason="invalid_period")
    gap_token = match.group("gap")
    gap = 10.0 if gap_token == "ten" else (float(gap_token) if gap_token else None)
    if gap is not None and not 0 < gap <= 600:
        return TypedQuery(eventFamily=event, unanswerable=True, reason="invalid_time_range")
    if event not in ALLOWED_EVENT_FAMILIES:
        return TypedQuery(eventFamily=event, unanswerable=True, reason="unknown_event_family")
    if successor and successor not in ALLOWED_EVENT_FAMILIES:
        return TypedQuery(eventFamily=event, unanswerable=True, reason="unknown_successor")
    successor_team_token = (match.group("successor_team") or "").lower()
    successor_team = {
        "our": "my_team",
        "my team": "my_team",
        "enemy": "enemy",
        "opponent": "opponent",
        "same": "same",
    }.get(successor_team_token)
    successor_constraint = (
        SuccessorConstraint(kind=successor, team=successor_team, period=period, withinSeconds=gap)
        if successor
        else None
    )
    outside = f"{stripped[:match.start()]} {stripped[match.end():]}"
    player_match = re.search(r"\bby player (?P<id>\d+)\b", outside, re.IGNORECASE)
    player_id = int(player_match.group("id")) if player_match else None
    if player_id is not None and player_id > 1_000_000:
        return TypedQuery(eventFamily=event, unanswerable=True, reason="invalid_player")
    if player_match:
        outside = outside.replace(player_match.group(), " ", 1)
    time_match = re.search(r"\bbetween (?P<start>\d+(?:\.\d+)?) and (?P<end>\d+(?:\.\d+)?) seconds\b",
        outside, re.IGNORECASE)
    start = float(time_match.group("start")) if time_match else None
    end = float(time_match.group("end")) if time_match else None
    if time_match:
        outside = outside.replace(time_match.group(), " ", 1)
    if start is not None and end is not None and (start > end or end > 86_400):
        return TypedQuery(eventFamily=event, unanswerable=True, reason="invalid_time_range",
            interpreted={"eventFamily": event, "timeStartSeconds": start, "timeEndSeconds": end})
    unsupported = [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9_'-]+", outside)
        if token.lower() not in {"show", "find", "list", "me", "all"}
    ]
    interpreted = {
        "team": team,
        "period": period,
        "eventFamily": event,
        "playerTrackId": player_id,
        "reviewStatus": match.group("review").lower() if match.group("review") else None,
        "timeStartSeconds": start,
        "timeEndSeconds": end,
        "successor": successor_constraint.model_dump(mode="json") if successor_constraint else None,
        "includeUnknown": include_unknown,
    }
    return TypedQuery(
        team=team,
        period=period,
        eventFamily=event,
        playerTrackId=player_id,
        reviewStatus=match.group("review").lower() if match.group("review") else None,
        timeStartSeconds=start,
        timeEndSeconds=end,
        successor=successor_constraint,
        includeUnknown=include_unknown,
        interpreted=interpreted,
        unsupportedTerms=unsupported,
        unanswerable=bool(unsupported),
        reason="unsupported_terms" if unsupported else None,
    )


def validate_query_proposal(raw: dict[str, Any], *, match_id: str, generation_id: str) -> TypedQuery:
    """Admit a model's filters only for the current scope and the existing executor."""
    if not isinstance(raw, dict) or set(raw) != {"matchId", "generationId", "query"} \
            or raw["matchId"] != match_id or raw["generationId"] != generation_id:
        raise ValueError("query proposal scope does not match")
    fields = raw["query"]
    allowed = {"eventFamily", "team", "playerTrackId", "period", "reviewStatus",
               "timeStartSeconds", "timeEndSeconds", "successor"}
    if not isinstance(fields, dict) or "eventFamily" not in fields or set(fields) - allowed:
        raise ValueError("unsupported query proposal predicate")
    return TypedQuery.model_validate(fields)


def execute_typed_query(events: list[dict[str, Any]], query: TypedQuery, *, match_id: str) -> list[SearchHit]:
    if query.unanswerable:
        return []
    hits: list[SearchHit] = []
    ordered = sorted(events, key=lambda item: float(item.get("timestamp") or 0.0))
    for index, event in enumerate(ordered):
        if _is_rejected_event(event):
            continue
        if not _matches_explicit(event.get("type"), query.eventFamily, query.includeUnknown, unknown=(None, "", "unknown")):
            continue
        if query.team and not _matches_explicit(event.get("team"), query.team, query.includeUnknown, unknown=(None, "", "unknown")):
            continue
        if query.period is not None and not _matches_explicit(event.get("period"), query.period, query.includeUnknown, unknown=(None, 0, "unknown")):
            continue
        if query.playerTrackId is not None and query.playerTrackId not in (event.get("fromTrackId"), event.get("toTrackId")):
            continue
        if query.reviewStatus is not None and event.get("reviewStatus") != query.reviewStatus:
            continue
        timestamp = event.get("timestamp")
        if query.timeStartSeconds is not None and not _at_or_after(timestamp, query.timeStartSeconds, query.includeUnknown):
            continue
        if query.timeEndSeconds is not None and not _at_or_before(timestamp, query.timeEndSeconds, query.includeUnknown):
            continue
        if query.successor:
            successor = _find_successor(ordered, index, query.successor, query.includeUnknown)
            if successor is None:
                continue
        hits.append(
            SearchHit(
                eventId=str(event.get("id") or f"{match_id}:{index}"),
                matchId=match_id,
                timestamp=float(event.get("timestamp") or 0.0),
                frameId=event.get("frameId"),
                intervalStart=event.get("intervalStart"),
                intervalEnd=event.get("intervalEnd"),
                reviewStatus=event.get("reviewStatus"),
                evidenceIds=list(event.get("evidenceIds") or []),
                label=str(event.get("type")),
            )
        )
    return hits


def _find_successor(
    events: list[dict[str, Any]],
    index: int,
    constraint: SuccessorConstraint,
    include_unknown: bool,
) -> dict[str, Any] | None:
    start = float(events[index].get("timestamp") or 0.0)
    for candidate in events[index + 1 :]:
        stamp = float(candidate.get("timestamp") or 0.0)
        if constraint.withinSeconds is not None and stamp - start > constraint.withinSeconds:
            return None
        if not _matches_explicit(candidate.get("type"), constraint.kind, include_unknown, unknown=(None, "", "unknown")):
            continue
        if constraint.period is not None and not _matches_explicit(
            candidate.get("period"), constraint.period, include_unknown, unknown=(None, 0, "unknown")
        ):
            continue
        expected_team = constraint.team
        if expected_team in {"same", "opponent"}:
            primary_team = events[index].get("team")
            if primary_team in ALLOWED_TEAMS:
                expected_team = primary_team if expected_team == "same" else ("enemy" if primary_team == "my_team" else "my_team")
            else:
                expected_team = None
        if expected_team and not _matches_explicit(
            candidate.get("team"), expected_team, include_unknown, unknown=(None, "", "unknown")
        ):
            continue
        if _is_rejected_event(candidate):
            continue
        return candidate
    return None


def _matches_explicit(actual: Any, expected: Any, include_unknown: bool, *, unknown: tuple[Any, ...]) -> bool:
    return actual == expected or (include_unknown and actual in unknown)


def _at_or_after(actual: Any, expected: float, include_unknown: bool) -> bool:
    return include_unknown if actual is None else float(actual) >= expected


def _at_or_before(actual: Any, expected: float, include_unknown: bool) -> bool:
    return include_unknown if actual is None else float(actual) <= expected


def _is_rejected_event(event: dict[str, Any]) -> bool:
    return str(event.get("reviewStatus") or "") == "rejected"


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


def events_as_query_rows(events: list[Any], *, match_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        payload = event.model_dump(mode="json") if hasattr(event, "model_dump") else dict(event)
        evidence_id = f"event:{payload.get('frameId')}:{payload.get('type')}:{payload.get('timestamp')}"
        payload["id"] = payload.get("id") or payload.get("eventId") or f"{match_id}:{index}"
        payload["evidenceIds"] = list(payload.get("evidenceIds") or payload.get("proposalEvidenceIds") or [evidence_id])
        rows.append(payload)
    return rows


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


def providers_disabled_fallback(
    *,
    metrics: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    template = template_report(metrics, events)
    return {
        "reviewOperational": True,
        "metricsOperational": True,
        "templateReportOperational": True,
        "route": "template",
        "reasonCodes": ["PROVIDER_DISABLED"],
        "output": template,
        "concealedPartialProcessing": False,
    }


class AssistanceRouter:
    def __init__(self, *, providers_enabled: bool = False, provider=None) -> None:
        self.providers_enabled = providers_enabled
        self.provider = provider
        self.calls = 0
        self.spend = 0.0
        self.reserved = 0.0

    def run(
        self,
        *,
        policy: AssistancePolicy,
        metrics: list[dict[str, Any]],
        events: list[dict[str, Any]],
        claimed_evidence_ids: list[str] | None = None,
        known_evidence_ids: set[str] | None = None,
        model_uncertain: bool = False,
        measured_quality_gap: bool = False,
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
        template = template_report(metrics, events)
        if policy.cloudPermitted:
            escalate = escalation_requires_quality_gap(
                model_uncertain=model_uncertain,
                measured_gap=measured_quality_gap,
            )
            if not escalate["escalate"]:
                return AssistanceDisposition(
                    route="template",
                    reasonCodes=list(escalate["reasonCodes"]),
                    output=template,
                )
        if not self.providers_enabled or not policy.allowedModelIds or policy.spendCap <= 0:
            return AssistanceDisposition(
                route="template",
                reasonCodes=["PROVIDER_DISABLED"],
                output=template,
            )
        reserved = max(0.0, policy.reservedCallCost)
        if self.calls >= policy.maxCalls or self.spend + self.reserved + reserved > policy.spendCap:
            reason = "SPEND_CAP" if self.spend + self.reserved + reserved > policy.spendCap else "PROVIDER_DISABLED"
            return AssistanceDisposition(
                route="template",
                reasonCodes=[reason],
                callsUsed=self.calls,
                spend=self.spend,
                output=template,
            )
        if self.provider is None:
            self.calls += 1
            return AssistanceDisposition(
                route="local" if not policy.cloudPermitted else "cloud",
                callsUsed=self.calls,
                spend=self.spend,
                output={"status": "provider_stub"},
            )
        self.reserved += reserved
        try:
            raw = self.provider(metrics=metrics, events=events, policy=policy)
        except TimeoutError:
            self.reserved -= reserved
            self.spend += reserved
            return AssistanceDisposition(
                route="template",
                reasonCodes=["PROVIDER_TIMEOUT"],
                callsUsed=self.calls,
                spend=self.spend,
                output=template,
            )
        except Exception:
            self.reserved -= reserved
            return AssistanceDisposition(
                route="template",
                reasonCodes=["PROVIDER_DISABLED"],
                callsUsed=self.calls,
                spend=self.spend,
                output=template,
            )
        self.reserved -= reserved
        self.spend += reserved
        self.calls += 1
        if not isinstance(raw, dict):
            repair = json_repair_chain(attempts=self.calls, max_repair=policy.maxRepairAttempts)
            reasons = ["MALFORMED_PROVIDER_OUTPUT"]
            if not repair["admitted"]:
                reasons.append("UNBOUNDED_JSON_REPAIR")
            return AssistanceDisposition(
                route="template",
                reasonCodes=reasons,
                callsUsed=self.calls,
                spend=self.spend,
                output=template,
            )
        validated = validate_output(
            raw,
            ApprovedEvidencePackage(
                match_id="assistance",
                generation_id="current",
                evidence_ids=frozenset(known),
                metrics=tuple(metrics),
                events=tuple(events),
                digest="",
            ),
        )
        if validated.grounding not in {"grounded", "referenced", "interpretive"}:
            return AssistanceDisposition(
                route="template",
                reasonCodes=list(validated.reason_codes),
                callsUsed=self.calls,
                spend=self.spend,
                output=template,
            )
        return AssistanceDisposition(
            route="local" if not policy.cloudPermitted else "cloud",
            reasonCodes=list(validated.reason_codes),
            callsUsed=self.calls,
            spend=self.spend,
            output=validated.payload,
        )


def dual_budgets(*, vision: float, language: float) -> dict[str, float]:
    return {"vision": vision, "language": language}


def embeddings_retrieve(query: str, *, passages: list[dict[str, Any]]) -> dict[str, Any]:
    del query, passages
    return {"enabled": False, "provesTacticalWeakness": False, "role": "candidate_retrieval_only"}


def policy_log(*, route: str, evidence_hash: str, secret: str) -> dict[str, Any]:
    del secret
    return {"route": route, "evidenceHash": evidence_hash, "policyVersion": "1", "secretsExcluded": True}


def preemptible_allowed(*, checkpoints: bool, restart_semantics: bool) -> bool:
    return bool(checkpoints and restart_semantics)


def network_failure_preserves_unknown(*, metric_value: float | None, generated_number: float) -> dict[str, Any]:
    del generated_number
    return {
        "value": metric_value,
        "availability": "unknown" if metric_value is None else "available",
        "replacedWithGenerated": False,
    }


def escalation_requires_quality_gap(*, model_uncertain: bool, measured_gap: bool) -> dict[str, Any]:
    del model_uncertain
    return {
        "escalate": bool(measured_gap),
        "reasonCodes": [] if measured_gap else ["ESCALATION_REQUIRES_MEASURED_QUALITY_GAP"],
    }


def json_repair_chain(*, attempts: int, max_repair: int) -> dict[str, Any]:
    admitted = attempts <= max_repair
    return {
        "admitted": admitted,
        "attempts": attempts,
        "maxRepair": max_repair,
        "reasonCodes": [] if admitted else ["UNBOUNDED_JSON_REPAIR"],
    }
