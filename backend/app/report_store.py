"""C03 immutable reports outside immutable analytical generations.

Lock order follows C01 (review, lifetime, publication). No provider runs under
these locks. SQLite's write reservation serialises live policy changes during the
short report commit; it is not a second analytical generation commit point.
"""
from __future__ import annotations

from datetime import datetime
import re
from pathlib import Path
from typing import NotRequired, TypedDict
import uuid

from .generations import GenerationRecoveryRequired, StaleGeneration, _identifier, _sync_directory
from .report_contracts import digest, EvidenceRef, ReportDraft, MetricClaim, ObservationClaim

TASKS = {"tactical_report", "drills"}


class _ReportNotice(TypedDict):
    code: str
    taskType: NotRequired[str]
    tasks: NotRequired[list[str]]


class StaleEvidenceGeneration(StaleGeneration):
    code = "STALE_EVIDENCE_GENERATION"


class StaleReportPolicy(StaleGeneration):
    code = "STALE_REPORT_POLICY"


def policy_revision(match, settings) -> str:
    from dataclasses import asdict
    spend_policy = getattr(settings, "provider_spend_policy", None)
    return digest({"rights": match.config.rights.model_dump(mode="json"),
                   "preferredProvider": match.config.llmProvider,
                   "homeTeam": match.config.homeTeam, "awayTeam": match.config.awayTeam,
                   "updatedAt": match.updatedAt.isoformat(),
                   "cloudEnabled": settings.cloud_provider_enabled,
                   "model": settings.cloud_model_id, "allowedModels": sorted(settings.allowed_model_ids),
                   "spendPolicy": asdict(spend_policy) if spend_policy is not None else None,
                   "callBudget": settings.provider_call_reservation, "totalBudget": settings.provider_budget_limit})


def validate_record(document, match_id: str, generation_id: str, task: str) -> None:
    """Validate optional persisted envelopes before they reach a renderer.

    The content digest detects accidental changes, not hostile local-store
    rewriting. Schema and scope checks remain necessary even with a valid digest.
    """
    if not isinstance(document, dict) or document.get("schemaVersion") != "report_record_v1":
        raise ValueError("Unsupported report record")
    if (document.get("matchId"), document.get("generationId"), document.get("taskType")) != (match_id, generation_id, task):
        raise ValueError("Report scope mismatch")
    for name in ("reportId", "modelId", "provider", "promptVersion", "outputSchema", "createdAt"):
        if not isinstance(document.get(name), str) or not document[name]:
            raise ValueError("Missing report identity: " + name)
    for name in ("inputEvidenceDigest", "policyRevision"):
        if not isinstance(document.get(name), str) or not re.fullmatch(r"[a-f0-9]{64}", document[name]):
            raise ValueError("Invalid report digest: " + name)
    if datetime.fromisoformat(document["createdAt"]).tzinfo is None:
        raise ValueError("Report timestamp must be timezone-aware")
    if not isinstance(document.get("metadata"), dict):
        raise ValueError("Invalid report metadata")
    payload = document.get("payload")
    if not isinstance(payload, dict) or (payload.get("matchId"), payload.get("generationId"), payload.get("inputEvidenceDigest")) != (match_id, generation_id, document["inputEvidenceDigest"]):
        raise ValueError("Report payload scope mismatch")
    grounding = payload.get("grounding")
    disposition = payload.get("validationDisposition", grounding)
    if disposition != document.get("validationDisposition") or disposition not in {"grounded", "referenced", "interpretive", "deterministic", "validation_failed"}:
        raise ValueError("Invalid report disposition")
    schema = payload.get("schemaVersion", "legacy_referenced_report_v0")
    if schema != document["outputSchema"]:
        raise ValueError("Stored output schema mismatch")
    if schema in {"report_draft_v1", "legacy_referenced_report_v0"}:
        _validate_narrative_payload(payload, match_id, generation_id, task, schema, disposition)
    elif schema == "deterministic_report_v1":
        if grounding != "deterministic" or disposition not in {"deterministic", "validation_failed"}:
            raise ValueError("Invalid deterministic report")
        if not isinstance(payload.get("summary"), str):
            raise ValueError("Malformed deterministic summary")
        for name in ("metrics", "events"):
            if not isinstance(payload.get(name), list) or any(not isinstance(item, dict) for item in payload[name]):
                raise ValueError("Malformed deterministic report")
    else:
        raise ValueError("Unsupported output schema")


def _validate_narrative_payload(payload, match_id, generation_id, task, schema, disposition):
    """Check the renderer's entire stored shape, including compatibility output.

    Provider aliases must already have been resolved before persistence. This
    checks shape, scope and label consistency, not free-text truth or protection
    against an attacker rewriting both the trusted store and its checksums.
    """
    server_fields = {"inputEvidenceDigest", "policy", "grounding", "validationDisposition",
                     "interpretationLabel", "requiresAnalyst"}
    if schema == "report_draft_v1":
        if set(payload) - (ReportDraft.model_fields.keys() | server_fields):
            raise ValueError("Unknown stored report fields")
        base = {key: value for key, value in payload.items() if key in ReportDraft.model_fields}
    else:
        allowed = {"schemaVersion", "matchId", "generationId", "summary", "interpretation",
                   "recommendations", "measurements", "evidence"} | server_fields
        if set(payload) - allowed:
            raise ValueError("Unknown compatibility report fields")
        summary = payload.get("summary", "")
        if not isinstance(summary, str):
            raise ValueError("Malformed compatibility summary")
        base = {"schemaVersion": "report_draft_v1", "matchId": match_id,
                "generationId": generation_id, "taskType": task,
                "metricClaims": payload.get("measurements", []),
                "observations": ([{"text": summary, "evidence": payload.get("evidence", []),
                                   "grounding": "referenced"}] if summary else []),
                "interpretation": payload.get("interpretation", ""),
                "recommendations": payload.get("recommendations", []),
                "evidence": payload.get("evidence", [])}
    for name, model in (("metricClaims", MetricClaim), ("observations", ObservationClaim)):
        items = base.get(name, [])
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise ValueError("Malformed stored report collection")
        extra = {"grounding", "availability", "publishedLabel"} if name == "metricClaims" else {"grounding"}
        for item in items:
            if set(item) - (model.model_fields.keys() | extra):
                raise ValueError("Unknown stored claim fields")
            expected = "grounded" if name == "metricClaims" else "referenced"
            if item.get("grounding") != expected:
                raise ValueError("Stored claim disposition mismatch")
            if name == "metricClaims" and item.get("availability") not in {"available", "experimental"}:
                raise ValueError("Stored metric claim is not publishable")
        base[name] = [{key: value for key, value in item.items() if key in model.model_fields} for item in items]
    parsed = ReportDraft.model_validate(base)
    if parsed.taskType != task or payload.get("requiresAnalyst") is not True:
        raise ValueError("Report task/review requirement mismatch")
    advice = bool(parsed.interpretation.strip() or parsed.recommendations or parsed.drills)
    expected = "referenced" if parsed.observations else "interpretive" if advice else "grounded"
    if not (parsed.metricClaims or parsed.observations or advice):
        raise ValueError("Empty stored report")
    if payload.get("grounding") != expected or disposition != expected:
        raise ValueError("Stored report disposition mismatch")
    refs = [*parsed.evidence]
    claims: list[MetricClaim | ObservationClaim] = [*parsed.metricClaims, *parsed.observations]
    for claim in claims:
        refs.extend(claim.evidence)
    for item in refs:
        # Parsed union still allows request aliases; persisted records do not.
        if not isinstance(item, EvidenceRef) or (item.matchId, item.generationId) != (match_id, generation_id):
            raise ValueError("Stored evidence reference scope mismatch")



class ReportStore:
    def __init__(self, storage):
        self.storage = storage

    def _directory(self, match_id: str, generation_id: str, task: str) -> Path:
        if task not in TASKS:
            raise ValueError("Unsupported report task")
        directory = self.storage.generations.root(match_id) / "reports" / _identifier(generation_id) / task
        # Local-store boundary: never follow an externally substituted path.
        for path in (directory, directory.parent, directory.parent.parent):
            if path.is_symlink():
                raise GenerationRecoveryRequired("Symlink report directory is not supported")
        return directory

    def publish(self, match_id, generation_id, task, payload, *, evidence_digest,
                policy, expected_policy_revision, settings, metadata=None) -> dict:
        from .storage import _utcnow
        gs = self.storage.generations
        with gs.guard(match_id, "review", exclusive=True), gs.guard(match_id, "lifetime"), \
                gs.guard(match_id, "publication", exclusive=True):
            if gs.resolve(match_id).generationId != generation_id:
                raise StaleEvidenceGeneration("Evidence changed during analysis; refresh before explicitly retrying")
            with self.storage._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                match = self.storage.get_match(match_id)
                if policy_revision(match, settings) != expected_policy_revision:
                    raise StaleReportPolicy("Match policy or report metadata changed during analysis")
                directory = self._directory(match_id, generation_id, task)
                directory.mkdir(parents=True, exist_ok=True)
                report_id = "report_" + uuid.uuid4().hex
                document = {"schemaVersion": "report_record_v1", "reportId": report_id,
                            "matchId": match_id, "generationId": generation_id,
                            "inputEvidenceDigest": evidence_digest, "taskType": task,
                            "modelId": policy.model_id, "provider": policy.provider,
                            "promptVersion": "scoped-report-prompt-v1",
                            "outputSchema": payload.get("schemaVersion", "legacy_referenced_report_v0"),
                            "validationDisposition": payload.get("validationDisposition", payload["grounding"]),
                            "policyRevision": expected_policy_revision,
                            "createdAt": _utcnow().isoformat(), "metadata": metadata or {}, "payload": payload}
                validate_record(document, match_id, generation_id, task)
                document["contentDigest"] = digest(document)
                self.storage._write_json(directory / f"{report_id}.json", document)
                _sync_directory(directory)
                _sync_directory(directory.parent)
                _sync_directory(directory.parent.parent)
                _sync_directory(gs.root(match_id))
                return {**document, "status": "current"}

    def view(self, match_id: str, *, generation_id: str | None = None) -> dict:
        gs = self.storage.generations
        with self.storage.generation_snapshot(match_id, generation_id=generation_id) as ref:
            # Inspect actual current pointer, not the caller's retained old pin.
            with gs.guard(match_id, "publication"):
                current = gs.resolve(match_id).generationId
            selected = ref.generationId
            historical = selected != current
            reports = {}
            notices: list[_ReportNotice] = []
            for task in sorted(TASKS):
                directory = self._directory(match_id, selected, task)
                candidates = []
                if directory.exists():
                    for path in directory.glob("report_*.json"):
                        try:
                            if path.is_symlink() or not path.is_file():
                                raise ValueError("Unsafe report member")
                            document = self.storage._read_json(path)
                            expected = document.get("contentDigest")
                            if digest({k:v for k,v in document.items() if k != "contentDigest"}) != expected:
                                raise ValueError("Report changed")
                            if (document.get("schemaVersion") != "report_record_v1"
                                or document.get("matchId") != match_id or document.get("generationId") != selected
                                or document.get("taskType") != task or path.stem != document.get("reportId")):
                                raise ValueError("Report scope mismatch")
                            validate_record(document, match_id, selected, task)
                            candidates.append(document)
                        except (ValueError, TypeError, AttributeError, OSError):
                            notices.append({"taskType": task, "code": "REPORT_VERIFICATION_REQUIRED"})
                if candidates:
                    # This orders optional reports *within one source generation*,
                    # never selects an analytical generation by directory timestamp.
                    document = max(candidates, key=lambda item: (item["createdAt"], item["reportId"]))
                    reports[task] = {**document, "status": "historical" if historical else "current"}
                else:
                    notices.append({"taskType": task, "code": "REPORT_UNAVAILABLE_FOR_GENERATION"})
            root = gs.root(match_id)
            legacy = [task for task in sorted(TASKS) if (root / f"{task}.json").is_file()]
            if legacy:
                notices.append({"code": "LEGACY_REPORTS_UNVERIFIED", "tasks": legacy})
            other = root / "reports"
            if other.is_dir() and any(p.is_dir() and p.name != selected for p in other.iterdir()):
                notices.append({"code": "OTHER_GENERATION_REPORTS_OMITTED"})
            return {"schemaVersion": "report_view_v1", "matchId": match_id, "generationId": selected,
                    "status": "historical" if historical else "current", "reports": reports, "notices": notices}

    def legacy(self, match_id: str, task: str) -> dict:
        if task not in TASKS:
            raise ValueError("Unsupported report task")
        path = self.storage.generations.root(match_id) / f"{task}.json"
        if path.is_symlink():
            raise GenerationRecoveryRequired("Symlink legacy report is not supported")
        payload = self.storage._read_json(path)
        return {"matchId": match_id, "generationId": None, "taskType": task,
                "status": "historical", "validationDisposition": "unverified", "payload": payload,
                "reasonCodes": ["LEGACY_SOURCE_GENERATION_UNKNOWN"]}
