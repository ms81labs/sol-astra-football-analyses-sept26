"""C03: request-scoped references and deliberately limited factual validation.

A valid reference is not proof that prose is true. Only structured, scoped
metric claims are grounded; observations remain referenced and advice interpretive.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class ReportShape(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class EvidenceRef(ReportShape):
    matchId: str
    generationId: str
    kind: Literal["frame", "event", "metric"]
    localId: str = Field(min_length=1)


class MetricClaim(ReportShape):
    metric: str
    definitionVersion: str
    teamScope: Literal["my_team", "enemy"] | None
    intervalStart: float
    intervalEnd: float
    unit: str
    value: float
    evidence: list[str | EvidenceRef] = Field(min_length=1)

    @field_validator("value", "intervalStart", "intervalEnd", mode="before")
    @classmethod
    def finite_number(cls, value):
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("A claim requires a finite JSON number, not a bool or numeric string")
        return float(value)


class ObservationClaim(ReportShape):
    text: str = Field(min_length=1)
    evidence: list[str | EvidenceRef] = Field(min_length=1)


class DrillAdvice(ReportShape):
    name: str
    objective: str
    setup: str
    duration: str


class ReportDraft(ReportShape):
    schemaVersion: Literal["report_draft_v1"]
    matchId: str
    generationId: str
    taskType: Literal["tactical_report", "drills"]
    metricClaims: list[MetricClaim] = Field(default_factory=list)
    observations: list[ObservationClaim] = Field(default_factory=list)
    interpretation: str = ""
    recommendations: list[str] = Field(default_factory=list)
    drills: list[DrillAdvice] = Field(default_factory=list)
    evidence: list[str | EvidenceRef] = Field(default_factory=list)


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def canonical_ref(value: dict) -> str:
    return json.dumps(EvidenceRef.model_validate(value).model_dump(), sort_keys=True, separators=(",", ":"))


def resolve_reference(value: Any, package) -> dict:
    aliases = getattr(package, "aliases", {})
    if isinstance(value, str):
        if value in aliases:
            return copy.deepcopy(aliases[value])
        # Compatibility for historical, server-constructed helper packages only.
        # New gateway packages always contain an alias map and NEVER accept bare IDs.
        if not aliases and value in package.evidence_ids:
            kind, sep, local = value.partition(":")
            if sep and kind in {"frame", "event", "metric"}:
                return {"matchId": package.match_id, "generationId": package.generation_id,
                        "kind": kind, "localId": local}
        raise ValueError("UNKNOWN_EVIDENCE_REFERENCE")
    if not isinstance(value, dict):
        raise ValueError("MALFORMED_EVIDENCE_REFERENCE")
    ref = EvidenceRef.model_validate(value).model_dump()
    if ref["matchId"] != package.match_id or ref["generationId"] != package.generation_id:
        raise ValueError("EVIDENCE_SCOPE_MISMATCH")
    permitted = {canonical_ref(item) for item in aliases.values()}
    if not aliases:
        permitted = {canonical_ref(resolve_reference(item, package)) for item in package.evidence_ids}
    if canonical_ref(ref) not in permitted:
        raise ValueError("UNKNOWN_EVIDENCE_REFERENCE")
    return ref


_REFERENCE_FIELDS = {"evidence", "evidenceIds", "references", "claimedEvidenceIds", "knownEvidenceIds"}


def validate_declared_references(value: Any, package) -> list[dict]:
    """Visit declared reference fields, NOT arbitrary prose/string prefixes."""
    refs: list[dict[str, object]] = []
    if isinstance(value, dict):
        for name, child in value.items():
            if name in _REFERENCE_FIELDS:
                if not isinstance(child, list):
                    raise ValueError("MALFORMED_EVIDENCE_REFERENCE")
                refs.extend(resolve_reference(item, package) for item in child)
            else:
                refs.extend(validate_declared_references(child, package))
    elif isinstance(value, list):
        for child in value:
            refs.extend(validate_declared_references(child, package))
    return refs


def validate_metric(claim: dict, package) -> dict:
    if not isinstance(claim, dict):
        raise ValueError("MALFORMED_PROVIDER_OUTPUT")
    required = {"metric", "definitionVersion", "teamScope", "intervalStart", "intervalEnd", "unit", "value", "evidence"}
    if not required <= claim.keys():
        raise ValueError("METRIC_SCOPE_REQUIRED")
    parsed = MetricClaim.model_validate(claim).model_dump()
    matches = [item for item in package.metrics if all(
        parsed[name] == item.get(name) for name in
        ("metric", "definitionVersion", "teamScope", "intervalStart", "intervalEnd", "unit"))]
    if len(matches) != 1:
        raise ValueError("METRIC_SCOPE_MISMATCH")
    expected = matches[0]
    number = expected.get("value")
    if expected.get("availability") not in {"available", "experimental"} or type(number) not in (int, float) or not math.isfinite(number):
        raise ValueError("METRIC_NOT_PUBLISHABLE")
    # Exact published JSON values by default. A future metric definition may
    # supply a server-owned precision; the provider cannot choose its tolerance.
    precision = expected.get("decimalPlaces")
    tolerance = 0.5 * 10 ** (-precision) if type(precision) is int and 0 <= precision <= 12 else 0.0
    if abs(parsed["value"] - number) > tolerance:
        raise ValueError("NUMERIC_CLAIM_MISMATCH")
    refs = [resolve_reference(item, package) for item in parsed["evidence"]]
    metric_ref = expected.get("reference")
    if metric_ref is None or metric_ref not in refs:
        raise ValueError("METRIC_REFERENCE_REQUIRED")
    return {**parsed, "evidence": refs, "availability": expected["availability"],
            "grounding": "grounded", "publishedLabel": expected.get("publishedLabel"),
            "eligibleSeconds": expected.get("eligibleSeconds"),
            "requestedSeconds": expected.get("requestedSeconds"),
            "denominator": expected.get("denominator"),
            "reasonCodes": copy.deepcopy(expected.get("reasonCodes", []))}


def check_output(raw: Any, package) -> tuple[dict, str, tuple[str, ...]]:
    if not isinstance(raw, dict):
        return {}, "unverified", ("MALFORMED_PROVIDER_OUTPUT",)
    try:
        # Non-finite values anywhere are rejected, including unrecognised fields.
        json.dumps(raw, allow_nan=False)
        refs = validate_declared_references(raw, package)
        schema = raw.get("schemaVersion")
        if schema == "report_draft_v1":
            parsed = ReportDraft.model_validate(raw).model_dump()
            if parsed["matchId"] != package.match_id or parsed["generationId"] != package.generation_id:
                raise ValueError("EVIDENCE_SCOPE_MISMATCH")
            if getattr(package, "task_type", None) not in (None, parsed["taskType"]):
                raise ValueError("TASK_SCHEMA_MISMATCH")
            metrics = [validate_metric(item, package) for item in parsed["metricClaims"]]
            observations = [{**item, "evidence": [resolve_reference(ref, package) for ref in item["evidence"]],
                             "grounding": "referenced"} for item in parsed["observations"]]
            advice = bool(parsed["interpretation"].strip() or parsed["recommendations"] or parsed["drills"])
            if not metrics and not observations and not advice:
                raise ValueError("EMPTY_REPORT")
            # Mixed reports cannot have all prose promoted to a measured fact.
            disposition = "referenced" if observations else "interpretive" if advice else "grounded"
            payload = {**parsed, "metricClaims": metrics, "observations": observations,
                       "evidence": refs, "grounding": disposition,
                       "interpretationLabel": "interpretive", "requiresAnalyst": True}
            return payload, disposition, (disposition.upper(),)
        if schema is not None:
            raise ValueError("UNSUPPORTED_REPORT_SCHEMA")
        # Small compatibility surface. Useful referenced prose remains readable,
        # but arbitrary old nested numeric output is no longer certified as fact.
        allowed = {"summary", "interpretation", "evidence", "recommendations", "measurements"}
        if set(raw) - allowed:
            raise ValueError("STRUCTURED_REPORT_SCHEMA_REQUIRED")
        if any(name in raw and not isinstance(raw[name], str) for name in ("summary", "interpretation")):
            raise ValueError("MALFORMED_PROVIDER_OUTPUT")
        advice = raw.get("recommendations", [])
        if not isinstance(advice, list) or any(not isinstance(item, str) for item in advice):
            raise ValueError("MALFORMED_PROVIDER_OUTPUT")
        claims = raw.get("measurements", [])
        if not isinstance(claims, list):
            raise ValueError("MALFORMED_PROVIDER_OUTPUT")
        checked = [validate_metric(item, package) for item in claims]
        if raw.get("summary") and not refs:
            raise ValueError("FACTUAL_REFERENCES_REQUIRED")
        if not raw.get("summary") and not checked and not raw.get("interpretation") and not advice:
            raise ValueError("EMPTY_REPORT")
        disposition = "referenced" if raw.get("summary") else "interpretive" if raw.get("interpretation") or advice else "grounded"
        return {**copy.deepcopy(raw), "evidence": refs, "measurements": checked,
                "grounding": disposition, "interpretationLabel": "interpretive", "requiresAnalyst": True}, disposition, (disposition.upper(),)
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        reason = str(exc) if not isinstance(exc, ValidationError) and str(exc).isupper() else "MALFORMED_PROVIDER_OUTPUT"
        return {}, "validation_failed", (reason,)


def deterministic_fallback(package, reasons: tuple[str, ...], *, failed: bool = True) -> dict:
    """Actual server facts, not an empty object advertised as a report."""
    metrics = [copy.deepcopy(item) for item in package.metrics]
    return {"kind": "deterministic_template", "schemaVersion": "deterministic_report_v1",
            "matchId": package.match_id, "generationId": package.generation_id,
            "summary": ("Provider output was not validated. Only stored measurements are shown." if failed
                        else "Stored publishable measurements; no model-generated factual claim is certified."),
            "grounding": "deterministic", "validationDisposition": "validation_failed" if failed else "deterministic",
            "reasonCodes": list(reasons), "metrics": metrics,
            "events": copy.deepcopy(list(package.events)), "requiresAnalyst": True}
