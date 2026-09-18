from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .settings import ProcessingSettings
from .workbench.evidence import records_from_match


_GATEWAY_SECRET = object()


class GatewayToken:
    __slots__ = ("_secret",)

    def __init__(self, secret: object) -> None:
        if secret is not _GATEWAY_SECRET:
            raise TypeError("GatewayToken is private to ProviderGateway")
        self._secret = secret


def is_valid_gateway_token(value: object) -> bool:
    return isinstance(value, GatewayToken) and value._secret is _GATEWAY_SECRET


@dataclass(frozen=True)
class ExecutionPolicy:
    match_id: str
    generation_id: str
    provider: str
    model_id: str
    processing_scope: str
    cloud_permitted: bool
    budget_reserved: float | None
    deadline_seconds: float
    reason_codes: tuple[str, ...]


class ProviderDenied(Exception):
    def __init__(self, reason_codes: list[str]) -> None:
        self.reason_codes = reason_codes
        super().__init__(", ".join(reason_codes))


@dataclass(frozen=True)
class ApprovedEvidencePackage:
    match_id: str
    generation_id: str
    evidence_ids: frozenset[str]
    metrics: tuple[dict[str, Any], ...]
    events: tuple[dict[str, Any], ...]
    digest: str


@dataclass(frozen=True)
class ValidatedOutput:
    payload: dict[str, Any]
    grounding: str
    reason_codes: tuple[str, ...]


class ProviderBudgetLedger:
    def __init__(self, path: Path, limit: float) -> None:
        self.path = path
        self.limit = limit
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS provider_reservations ("
                "id INTEGER PRIMARY KEY, match_id TEXT NOT NULL, task_type TEXT NOT NULL, amount REAL NOT NULL)"
            )

    def reserve(self, *, match_id: str, task_type: str, amount: float) -> float | None:
        if not math.isfinite(amount) or amount <= 0:
            return None
        with sqlite3.connect(self.path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            spent = float(connection.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM provider_reservations"
            ).fetchone()[0])
            if spent + amount > self.limit:
                return None
            connection.execute(
                "INSERT INTO provider_reservations(match_id, task_type, amount) VALUES (?, ?, ?)",
                (match_id, task_type, amount),
            )
        return amount

    def reservations(self) -> list[dict[str, object]]:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                "SELECT match_id, task_type, amount FROM provider_reservations ORDER BY id"
            ).fetchall()
        return [
            {"matchId": match_id, "taskType": task_type, "amount": amount}
            for match_id, task_type, amount in rows
        ]


class ProviderGateway:
    def __init__(self, storage, settings: ProcessingSettings, *, adapter_factory, budget_ledger=None) -> None:
        self.storage = storage
        self.settings = settings
        self.adapter_factory = adapter_factory
        self.budget_ledger = budget_ledger
        self._token = GatewayToken(_GATEWAY_SECRET)

    def resolve_policy(
        self,
        match,
        *,
        requested_provider: str | None,
        task_type: str,
        generation_id: str,
        require_provider: bool,
    ) -> ExecutionPolicy:
        requested = requested_provider or match.config.llmProvider
        if requested not in {"local", "cloud"}:
            raise ProviderDenied(["UNKNOWN_PROVIDER"])
        rights = match.config.rights
        policy_reasons: list[str] = []
        if requested == "cloud":
            match_reasons = []
            if not rights.cloudPermission:
                match_reasons.append("CLOUD_NOT_PERMITTED")
            if rights.processingScope == "local_only":
                match_reasons.append("SCOPE_LOCAL_ONLY")
            if match_reasons:
                if require_provider:
                    raise ProviderDenied(match_reasons)
                policy_reasons.extend(match_reasons)
                requested = "local"
            else:
                reasons = []
                if not self.settings.cloud_provider_enabled:
                    reasons.append("CLOUD_PROVIDER_DISABLED")
                if not self.settings.cloud_provider_api_key:
                    reasons.append("CLOUD_CREDENTIALS_MISSING")
                if self.settings.cloud_model_id not in self.settings.allowed_model_ids:
                    reasons.append("MODEL_NOT_ALLOWLISTED")
                if self.budget_ledger is None:
                    reasons.append("BUDGET_EXHAUSTED")
                if reasons:
                    if require_provider:
                        raise ProviderDenied(reasons)
                    policy_reasons.extend(reasons)
                    requested = "local"

        reserved = None
        if requested == "cloud":
            reserved = self.budget_ledger.reserve(
                match_id=match.id,
                task_type=task_type,
                amount=self.settings.provider_call_reservation,
            )
            if reserved is None:
                if require_provider:
                    raise ProviderDenied(["BUDGET_EXHAUSTED"])
                policy_reasons.append("BUDGET_EXHAUSTED")
                requested = "local"
        return ExecutionPolicy(
            match_id=match.id,
            generation_id=generation_id,
            provider=requested,
            model_id=self.settings.cloud_model_id,
            processing_scope=rights.processingScope,
            cloud_permitted=requested == "cloud",
            budget_reserved=reserved,
            deadline_seconds=self.settings.provider_deadline_seconds,
            reason_codes=tuple(policy_reasons),
        )

    def build_evidence(self, match_id: str, generation_id: str) -> tuple[ApprovedEvidencePackage, dict[str, Any]]:
        frames = self.storage.load_frames(match_id, generation_id=generation_id)
        try:
            events = self.storage.load_events(match_id, generation_id=generation_id)
        except FileNotFoundError:
            events = []
        try:
            summary, _, formation_timeline, shots = self.storage.load_analytics(
                match_id, generation_id=generation_id
            )
            metrics = tuple(item.model_dump(mode="json") for item in summary.metricAvailability)
        except FileNotFoundError:
            summary, formation_timeline, shots, metrics = None, None, None, ()
        event_payloads = tuple(item.model_dump(mode="json") for item in events)
        evidence = records_from_match(frames, events)
        canonical = {
            "matchId": match_id,
            "generationId": generation_id,
            "evidenceIds": sorted(item.evidenceId for item in evidence),
            "metrics": metrics,
            "events": event_payloads,
        }
        package = ApprovedEvidencePackage(
            match_id=match_id,
            generation_id=generation_id,
            evidence_ids=frozenset(canonical["evidenceIds"]),
            metrics=metrics,
            events=event_payloads,
            digest=hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        )
        return package, {
            "frames": frames,
            "summary": summary,
            "events": events,
            "formation_timeline": formation_timeline,
            "shots": shots,
        }

    def execute(
        self,
        match_id: str,
        task_type: str,
        *,
        requested_provider: str | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        match = self.storage.get_match(match_id)
        with self.storage.generation_snapshot(match_id) as generation:
            generation_id = generation.generationId
            policy = self.resolve_policy(
                match,
                requested_provider=requested_provider,
                task_type=task_type,
                generation_id=generation_id,
                require_provider=bool((body or {}).get("requireProvider")),
            )
            package, inputs = self.build_evidence(match_id, generation_id)
        raw = self.adapter_factory()(
            task_type,
            inputs["frames"],
            provider=policy.provider,
            attack_direction=match.config.attackDirection,
            current_frame_index=(body or {}).get("currentFrameIndex"),
            summary=inputs["summary"],
            events=inputs["events"],
            formation_timeline=inputs["formation_timeline"],
            shots=inputs["shots"],
            gateway_token=self._token,
            model_id=policy.model_id,
            deadline_seconds=policy.deadline_seconds,
        )
        validated = validate_output(raw, package)
        response = validated.payload if validated.grounding == "grounded" else {
            "kind": "deterministic_template",
            "reasonCodes": list(validated.reason_codes),
            "grounding": "ungrounded",
        }
        return {
            **response,
            "policy": {"provider": policy.provider, "reasonCodes": list(policy.reason_codes)},
        }


def _walk(value: Any):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def validate_output(raw: Any, package: ApprovedEvidencePackage) -> ValidatedOutput:
    if not isinstance(raw, dict) or not isinstance(raw.get("evidence", []), list):
        return ValidatedOutput({}, "ungrounded", ("MALFORMED_PROVIDER_OUTPUT",))

    references = {
        item
        for item in _walk(raw)
        if isinstance(item, str) and item.startswith(("ev_", "event:", "frame:"))
    }
    if not references.issubset(package.evidence_ids):
        return ValidatedOutput({}, "ungrounded", ("UNKNOWN_EVIDENCE_REFERENCE",))

    known_metrics = {
        str(item["metric"]): item.get("value")
        for item in package.metrics
        if item.get("metric") is not None
    }
    for node in _walk(raw):
        if not isinstance(node, dict):
            continue
        metric = node.get("metric")
        value = node.get("value")
        if metric is not None and isinstance(value, (int, float)):
            expected = known_metrics.get(str(metric))
            if expected is None or abs(float(value) - float(expected)) > 1e-6:
                return ValidatedOutput({}, "ungrounded", ("NUMERIC_CLAIM_MISMATCH",))
        for metric_name, expected in known_metrics.items():
            direct_value = node.get(metric_name)
            if isinstance(direct_value, (int, float)) and (
                expected is None or abs(float(direct_value) - float(expected)) > 1e-6
            ):
                return ValidatedOutput({}, "ungrounded", ("NUMERIC_CLAIM_MISMATCH",))

    payload = dict(raw)
    if "interpretation" in payload:
        payload["interpretationLabel"] = "interpretive"
    payload["grounding"] = "grounded"
    return ValidatedOutput(payload, "grounded", ("GROUNDED",))
