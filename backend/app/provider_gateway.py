from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .settings import ProcessingSettings
from .provider_adapters import LOCAL_MODEL_ID
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
    aliases: dict[str, dict] = field(default_factory=dict)
    task_type: str | None = None
    frame_samples: tuple[dict[str, Any], ...] = ()


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
            model_id=self.settings.cloud_model_id if requested == "cloud" else LOCAL_MODEL_ID,
            processing_scope=rights.processingScope,
            cloud_permitted=requested == "cloud",
            budget_reserved=reserved,
            deadline_seconds=self.settings.provider_deadline_seconds,
            reason_codes=tuple(policy_reasons),
        )

    def build_evidence(self, match_id: str, generation_id: str, task_type: str | None = None) -> tuple[ApprovedEvidencePackage, dict[str, Any]]:
        from .report_contracts import digest
        with self.storage.generation_snapshot(match_id, generation_id=generation_id):
            frames = self.storage.load_frames(match_id, generation_id=generation_id)
            events = self.storage.load_events(match_id, generation_id=generation_id)
            summary, _, formation_timeline, shots = self.storage.load_analytics(match_id, generation_id=generation_id)
            records = records_from_match(frames, events)
            # Duplicate local IDs cannot be treated as unambiguous evidence.
            # Preserve the legacy cursor format, but refuse provider dispatch
            # rather than silently merging two different observations.
            ids = [record.evidenceId for record in records]
            if len(ids) != len(set(ids)):
                raise ProviderDenied(["AMBIGUOUS_EVIDENCE_IDS"])
            aliases: dict[str, dict] = {}
            def permit(kind, local_id):
                ref = {"matchId": match_id, "generationId": generation_id, "kind": kind, "localId": local_id}
                alias = "ref_" + digest({"task": task_type, **ref})
                aliases[alias] = ref
                return ref, alias
            for record in records:
                if record.reviewStatus in {"rejected", "superseded"} or record.supersededBy:
                    continue
                kind, _, local_id = record.evidenceId.partition(":")
                if kind in {"event", "frame"}:
                    permit(kind, local_id)
            start = float(frames[0].timestamp) if frames else 0.0
            end = math.nextafter(float(frames[-1].timestamp), math.inf) if frames else 0.0
            metrics = []
            for index, record in enumerate(summary.metricAvailability):
                item = record.model_dump(mode="json")
                # Never expose withheld backing values as publishable evidence.
                if item["availability"] not in {"available", "experimental"}:
                    item["value"] = None
                item.update(intervalStart=start, intervalEnd=end)
                ref, alias = permit("metric", str(index) + ":" + item["metric"])
                item.update(reference=ref, evidence=[alias] if item["value"] is not None else [])
                if item["value"] is None:
                    aliases.pop(alias)
                metrics.append(item)
            event_payloads = tuple(item.model_dump(mode="json") for item in events if item.reviewStatus != "rejected")
            from .llm import _sample_frames
            samples = tuple(_sample_frames(frames))
            canonical = {"matchId": match_id, "generationId": generation_id, "taskType": task_type,
                         "frameSamples": samples,
                         "aliases": aliases, "metrics": metrics, "events": event_payloads}
            package = ApprovedEvidencePackage(match_id, generation_id, frozenset(aliases),
                                              tuple(metrics), event_payloads, digest(canonical), aliases, task_type, samples)
            return package, {"frames": frames, "summary": summary, "events": events,
                             "formation_timeline": formation_timeline, "shots": shots}

    def execute(self, match_id: str, task_type: str, *, requested_provider: str | None = None,
                body: dict[str, Any] | None = None) -> dict[str, Any]:
        import copy
        from .report_contracts import deterministic_fallback
        from .report_store import ReportStore, TASKS, StaleEvidenceGeneration, policy_revision
        if task_type not in TASKS:
            raise ValueError("Unsupported report task")
        body = body or {}
        with self.storage.generation_snapshot(match_id) as generation:
            generation_id = generation.generationId
            if body.get("generationId") not in (None, generation_id):
                raise StaleEvidenceGeneration("Select the current generation before requesting a report")
            analytical_match = self.storage.get_match(match_id)
            package, inputs = self.build_evidence(match_id, generation_id, task_type)
        # Live policy is read immediately before dispatch, never restored from G.
        with self.storage.generations.guard(match_id, "publication"):
            if self.storage.generations.resolve(match_id).generationId != generation_id:
                raise StaleEvidenceGeneration("Evidence changed before dispatch")
            live_match = self.storage.get_match(match_id)
        revision = policy_revision(live_match, self.settings)
        policy = self.resolve_policy(live_match, requested_provider=requested_provider, task_type=task_type,
                                     generation_id=generation_id, require_provider=bool(body.get("requireProvider")))
        raw = self.adapter_factory()(
            task_type, inputs["frames"], provider=policy.provider,
            attack_direction=analytical_match.config.attackDirection,
            current_frame_index=body.get("currentFrameIndex"), summary=inputs["summary"],
            events=inputs["events"], formation_timeline=inputs["formation_timeline"], shots=inputs["shots"],
            gateway_token=self._token, model_id=policy.model_id, deadline_seconds=policy.deadline_seconds,
            approved_evidence=copy.deepcopy({"matchId": match_id, "generationId": generation_id,
                "taskType": task_type, "inputEvidenceDigest": package.digest,
                "aliases": package.aliases, "metrics": package.metrics, "events": package.events,
                "frameSamples": package.frame_samples}))
        validated = validate_output(raw, package)
        response = validated.payload if validated.grounding in {"grounded", "referenced", "interpretive"} else deterministic_fallback(package, validated.reason_codes)
        response = {**response, "matchId": match_id, "generationId": generation_id,
                    "inputEvidenceDigest": package.digest,
                    "policy": {"provider": policy.provider, "reasonCodes": list(policy.reason_codes)}}
        # A stale/malformed result never refunds a possibly incurred reservation.
        # C04 owns settlement; C03 does not invent a no-charge determination.
        record = ReportStore(self.storage).publish(match_id, generation_id, task_type, response,
            evidence_digest=package.digest, policy=policy, expected_policy_revision=revision,
            settings=self.settings, metadata={"title": live_match.name,
                "homeTeam": live_match.config.homeTeam, "awayTeam": live_match.config.awayTeam})
        return {**response, "reportId": record["reportId"], "status": record["status"],
                "validationDisposition": record["validationDisposition"]}


def validate_output(raw: Any, package: ApprovedEvidencePackage) -> ValidatedOutput:
    from .report_contracts import check_output
    return ValidatedOutput(*check_output(raw, package))
