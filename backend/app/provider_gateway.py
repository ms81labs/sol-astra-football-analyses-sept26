from __future__ import annotations

import hashlib
import json
import math
import uuid
from dataclasses import dataclass, field
from typing import Any

from .settings import ProcessingSettings
from .provider_adapters import LOCAL_MODEL_ID
from .provider_billing import (AstraSpendPolicy, ProviderBudgetLedger as ProviderBudgetLedger,
                               ProviderTicket, ProviderResult, ProviderNotDispatched)
from .workbench.money import money
from .workbench.jobs import maintain_job_lease
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
    execution_bound: dict | None = None
    ticket: ProviderTicket | None = None


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
    visual_images: tuple[dict[str, Any], ...] = ()
    image_manifest_digest: str | None = None


@dataclass(frozen=True)
class ValidatedOutput:
    payload: dict[str, Any]
    grounding: str
    reason_codes: tuple[str, ...]


class ProviderGateway:
    def __init__(self, storage, settings: ProcessingSettings, *, adapter_factory, budget_ledger=None) -> None:
        self.storage = storage
        self.settings = settings
        self.adapter_factory = adapter_factory
        self.budget_ledger = budget_ledger
        self._token = GatewayToken(_GATEWAY_SECRET)

    def event_proposal_available(self, match) -> bool:
        return match.inputMode == "video" and self.proposal_available(match, "event_proposal")

    def proposal_available(self, match, task_type: str) -> bool:
        spend = self.settings.provider_spend_policy
        return (match.config.rights.cloudPermission
            and match.config.rights.processingScope != "local_only"
            and self.settings.cloud_provider_enabled and bool(self.settings.cloud_provider_api_key)
            and self.settings.cloud_model_id in self.settings.allowed_model_ids
            and isinstance(spend, AstraSpendPolicy) and task_type in spend.task_types
            and self.budget_ledger is not None)

    def resolve_policy(
        self,
        match,
        *,
        requested_provider: str | None,
        task_type: str,
        generation_id: str,
        require_provider: bool,
        prompt: str | None = None,
        request_id: str | None = None,
        source_identity: str = "",
        adapter=None,
        retry_of_attempt_id: str | None = None,
        visual_images: tuple[dict[str, Any], ...] = (),
        prepared_request: dict[str, Any] | None = None,
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
        bound = None
        ticket = None
        if requested == "cloud":
            spend = self.settings.provider_spend_policy
            adapter = self.adapter_factory() if adapter is None else adapter
            reasons = []
            if spend is None or getattr(adapter, "billing_contract_id", None) != spend.adapter_id:
                reasons.append("CLOUD_SPEND_BOUND_UNQUALIFIED")
            elif isinstance(spend, AstraSpendPolicy) and prepared_request is None:
                reasons.append("REQUEST_BOUND_MISSING")
            elif not isinstance(spend, AstraSpendPolicy) and visual_images:
                reasons.append("CLOUD_SPEND_BOUND_UNQUALIFIED")
            elif not isinstance(spend, AstraSpendPolicy) and prompt is None:
                reasons.append("REQUEST_BOUND_MISSING")
            else:
                try:
                    bound = (spend.bind_request(prepared_request, task=task_type,
                        model=self.settings.cloud_model_id,
                        authorised_limit=str(self.settings.provider_call_reservation))
                        if isinstance(spend, AstraSpendPolicy) else
                        spend.bind(prompt=prompt, task=task_type, model=self.settings.cloud_model_id))
                    if task_type in {"event_proposal", "query_proposal"}:
                        bound = {**bound, "generationId": generation_id,
                                 "modelVersion": self.settings.cloud_model_id}
                    if money(bound["maximumCost"]) > money(self.settings.provider_call_reservation):
                        reasons.append("REQUEST_BOUND_EXCEEDS_AUTHORISED_BUDGET")
                except ValueError as exc:
                    reasons.append(str(exc))
            if not reasons:
                ticket = self.budget_ledger.admit(match_id=match.id, task_type=task_type,
                    request_id=request_id or "provider:" + str(uuid.uuid4()),
                    source_identity=source_identity, execution_bound=bound,
                    authorised_budget=self.settings.provider_call_reservation, retry_of_attempt_id=retry_of_attempt_id)
                if ticket is None:
                    reasons.append("BUDGET_EXHAUSTED")
                else:
                    reserved = ticket.attempt.reservedCost
            if reasons:
                if require_provider:
                    raise ProviderDenied(reasons)
                policy_reasons.extend(reasons)
                requested, bound, ticket = "local", None, None
        return ExecutionPolicy(
            match_id=match.id,
            generation_id=generation_id,
            provider=requested,
            model_id=self.settings.cloud_model_id if requested == "cloud" else LOCAL_MODEL_ID,
            processing_scope=rights.processingScope,
            cloud_permitted=requested == "cloud",
            budget_reserved=reserved,
            deadline_seconds=self.settings.provider_deadline_seconds,
            reason_codes=tuple(policy_reasons), execution_bound=bound, ticket=ticket,
        )

    def build_evidence(self, match_id: str, generation_id: str, task_type: str | None = None,
                       *, image_manifest_digest: str | None = None) -> tuple[ApprovedEvidencePackage, dict[str, Any]]:
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
                event = record.payload.get("event") if isinstance(record.payload, dict) else None
                if event and event.get("proposalModelId") and not event.get("proposalRequestId"):
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
            event_payloads = tuple(item.model_dump(mode="json") for item in events
                if item.reviewStatus != "rejected" and (not item.proposalModelId or item.proposalRequestId))
            from .llm import _sample_frames
            samples = tuple(_sample_frames(frames))
            visual_images = ()
            image_payloads = ()
            if image_manifest_digest is not None:
                from .provider_images import load_image_manifest
                from .workbench.artifacts import ArtifactStore
                if not isinstance(image_manifest_digest, str) or self.storage.get_match(match_id).inputMode != "video":
                    raise ValueError("provider images require a retained video source and manifest digest")
                store = ArtifactStore(self.storage.storage_root / "artifacts")
                try:
                    resolved = load_image_manifest(store, image_manifest_digest,
                        match_id=match_id, generation_id=generation_id,
                        source_sha256=self.storage.source_sha256(match_id),
                        source_frames={item.frameId: item.timestamp for item in frames})
                except KeyError as exc:
                    raise ValueError("unknown provider image manifest") from exc
                visual_images = tuple(ref.model_dump(mode="json") for ref, _ in resolved)
                image_payloads = tuple(payload for _, payload in resolved)
            canonical = {"matchId": match_id, "generationId": generation_id, "taskType": task_type,
                         "frameSamples": samples,
                         "aliases": aliases, "metrics": metrics, "events": event_payloads}
            if visual_images:
                canonical.update(visualImages=visual_images, imageManifestDigest=image_manifest_digest)
            package = ApprovedEvidencePackage(match_id, generation_id, frozenset(aliases),
                                              tuple(metrics), event_payloads, digest(canonical), aliases, task_type,
                                              samples, visual_images, image_manifest_digest)
            return package, {"frames": frames, "summary": summary, "events": events,
                             "formation_timeline": formation_timeline, "shots": shots,
                             "visual_image_payloads": image_payloads}

    def execute(self, match_id: str, task_type: str, *, requested_provider: str | None = None,
                body: dict[str, Any] | None = None) -> dict[str, Any]:
        import copy
        from .report_contracts import deterministic_fallback
        from .report_store import ReportStore, TASKS, StaleEvidenceGeneration, StaleReportPolicy, policy_revision
        if task_type not in TASKS:
            raise ValueError("Unsupported report task")
        body = body or {}
        retry = body.get("retry", False)
        retry_anchor = body.get("retryOfAttemptId")
        if type(retry) is not bool:
            raise ValueError("retry must be a boolean")
        if retry and (not isinstance(retry_anchor, str) or not retry_anchor or len(retry_anchor) > 128):
            from .workbench.errors import ReconciliationRequired
            raise ReconciliationRequired("explicit retry requires retryOfAttemptId from its receipt")
        if not retry and retry_anchor is not None:
            raise ValueError("retryOfAttemptId requires explicit retry")
        with self.storage.generation_snapshot(match_id) as generation:
            generation_id = generation.generationId
            if body.get("generationId") not in (None, generation_id):
                raise StaleEvidenceGeneration("Select the current generation before requesting a report")
            analytical_match = self.storage.get_match(match_id)
            if body.get("imageManifestDigest") is None:
                package, inputs = self.build_evidence(match_id, generation_id, task_type)
            else:
                package, inputs = self.build_evidence(match_id, generation_id, task_type,
                    image_manifest_digest=body["imageManifestDigest"])
        # Live policy is read immediately before dispatch, never restored from G.
        with self.storage.generations.guard(match_id, "publication"):
            if self.storage.generations.resolve(match_id).generationId != generation_id:
                raise StaleEvidenceGeneration("Evidence changed before dispatch")
            live_match = self.storage.get_match(match_id)
        revision = policy_revision(live_match, self.settings)
        from .llm import build_prompt
        approved = copy.deepcopy({"matchId": match_id, "generationId": generation_id,
            "taskType": task_type, "inputEvidenceDigest": package.digest,
            "aliases": package.aliases, "metrics": package.metrics, "events": package.events,
            "frameSamples": package.frame_samples})
        if package.visual_images:
            approved.update(visualImages=package.visual_images,
                            imageManifestDigest=package.image_manifest_digest)
        frame_index = body.get("currentFrameIndex")
        if frame_index is not None and (type(frame_index) is not int or not 0 <= frame_index < len(inputs["frames"])):
            raise ValueError("Invalid current frame index")
        prompt = build_prompt(task_type, inputs["frames"],
            current_frame=inputs["frames"][frame_index] if frame_index is not None else None,
            summary=inputs["summary"], events=inputs["events"],
            formation_timeline=inputs["formation_timeline"], shots=inputs["shots"],
            attack_direction=analytical_match.config.attackDirection, approved_evidence=approved)
        adapter = self.adapter_factory()
        # Keyless legacy callers replay one logical request for these immutable inputs.
        # An explicitly new request must use a new caller ID, never an automatic retry.
        key = body["requestId"] if "requestId" in body else "auto:" + hashlib.sha256(
            json.dumps([task_type, package.digest, requested_provider or live_match.config.llmProvider,
                        self.settings.cloud_model_id, frame_index]).encode()).hexdigest()
        if not isinstance(key, str) or not 1 <= len(key) <= 256:
            raise ValueError("Invalid provider request ID")
        request_id = "provider:" + hashlib.sha256(json.dumps([match_id, key]).encode()).hexdigest()
        prepared_request = None
        spend = self.settings.provider_spend_policy
        if (requested_provider or live_match.config.llmProvider) == "cloud" and isinstance(spend, AstraSpendPolicy) \
                and getattr(adapter, "billing_contract_id", None) == spend.adapter_id:
            from .provider_adapters import build_astra_request
            from .provider_images import ProviderImage
            images = [(ProviderImage.model_validate_json(json.dumps(ref)), payload) for ref, payload in
                zip(package.visual_images, inputs["visual_image_payloads"], strict=True)]
            prepared_request = build_astra_request(prompt, images,
                approved_images=package.visual_images, max_output_tokens=spend.max_output_tokens)
        policy = self.resolve_policy(live_match, requested_provider=requested_provider, task_type=task_type,
            generation_id=generation_id, require_provider=bool(body.get("requireProvider")),
            prompt=prompt, request_id=request_id, source_identity=package.digest, adapter=adapter,
            retry_of_attempt_id=retry_anchor, visual_images=package.visual_images,
            prepared_request=prepared_request)
        ticket = policy.ticket
        if ticket is not None:
            with self.storage.generations.guard(match_id, "publication"):
                stale_generation = self.storage.generations.resolve(match_id).generationId != generation_id
                stale_policy = policy_revision(self.storage.get_match(match_id), self.settings) != revision
                if stale_generation or stale_policy:
                    current = self.budget_ledger.ledger.latest_attempt(request_id)
                    self.budget_ledger.ledger.transition(current.attemptId, expected_revision=current.revision,
                        owner_id=ticket.owner_id, status="failed", noChargeReason="NO_DISPATCH_CONFIRMED",
                        error="STALE_EVIDENCE_GENERATION" if stale_generation else "STALE_REPORT_POLICY")
                    if stale_generation:
                        raise StaleEvidenceGeneration("Evidence changed before dispatch")
                    raise StaleReportPolicy("Policy changed before dispatch")
                original = self.budget_ledger.result(request_id)
                if original is not None:
                    return original
                self.budget_ledger.claim(ticket)
        kwargs = dict(provider=policy.provider, attack_direction=analytical_match.config.attackDirection,
            current_frame_index=frame_index, summary=inputs["summary"], events=inputs["events"],
            formation_timeline=inputs["formation_timeline"], shots=inputs["shots"],
            gateway_token=self._token, model_id=policy.model_id, deadline_seconds=policy.deadline_seconds,
            approved_evidence=approved)
        if ticket is not None:
            kwargs.update(prepared_prompt=prompt, execution_bound=copy.deepcopy(policy.execution_bound),
                          request_id=request_id, reservation_id=ticket.attempt.attemptId)
            if prepared_request is not None:
                kwargs["prepared_request"] = copy.deepcopy(prepared_request)
        try:
            if ticket is not None:
                with maintain_job_lease(self.budget_ledger.ledger, request_id, owner_id=ticket.owner_id):
                    raw = adapter(task_type, inputs["frames"], **kwargs)
            else:
                raw = adapter(task_type, inputs["frames"], **kwargs)
        except BaseException as exc:
            if ticket is not None:
                ledger = self.budget_ledger.ledger
                current = ledger.latest_attempt(request_id)
                ledger.transition(current.attemptId, expected_revision=current.revision, owner_id=ticket.owner_id,
                    status="failed" if isinstance(exc, ProviderNotDispatched) else "outcome_unknown",
                    noChargeReason="NO_DISPATCH_CONFIRMED" if isinstance(exc, ProviderNotDispatched) else None,
                    error="NO_DISPATCH_CONFIRMED" if isinstance(exc, ProviderNotDispatched) else "PROVIDER_OUTCOME_UNKNOWN")
            raise
        if ticket is not None:
            ledger = self.budget_ledger.ledger
            current = ledger.latest_attempt(request_id)
            ledger.transition(current.attemptId, expected_revision=current.revision, owner_id=ticket.owner_id,
                              status="complete")
            # Preserve verified billing before validating/rendering/publishing optional prose.
            if isinstance(raw, ProviderResult) and raw.usage is not None:
                usage = raw.usage
                ledger.reconcile_attempt(current.attemptId, provider_outcome="complete", settled_cost=usage.total,
                    billing_complete=usage.final, receipt_id=request_id + ":" + usage.receipt_id)
        if isinstance(raw, ProviderResult):
            raw = raw.output
        validated = validate_output(raw, package)
        response = validated.payload if validated.grounding in {"grounded", "referenced", "interpretive"} else deterministic_fallback(package, validated.reason_codes)
        response = {**response, "matchId": match_id, "generationId": generation_id,
                    "inputEvidenceDigest": package.digest,
                    "policy": {"provider": policy.provider, "reasonCodes": list(policy.reason_codes)}}
        # Report publication cannot erase an invoice or imply an unknown request was free.
        record = ReportStore(self.storage).publish(match_id, generation_id, task_type, response,
            evidence_digest=package.digest, policy=policy, expected_policy_revision=revision,
            settings=self.settings, metadata={"title": live_match.name,
                "homeTeam": live_match.config.homeTeam, "awayTeam": live_match.config.awayTeam})
        result = {**response, "reportId": record["reportId"], "status": record["status"],
                  "validationDisposition": record["validationDisposition"]}
        if ticket is not None:
            result.update(requestId=request_id, costSummary=self.budget_ledger.ledger.cost_for(request_id))
            self.budget_ledger.save_result(request_id, result)
        return result

    def _dispatch_proposal(self, match_id: str, task_type: str, *, generation_id: str,
                           source_sha: str, revision: str, live_match, prompt: str,
                           request_key: str, frames: list, images: tuple[dict, ...] = (),
                           image_payloads: tuple[bytes, ...] = ()) -> tuple[dict, str, ExecutionPolicy, bool]:
        """Use the same rights, reservation, replay and uncertain-billing path for proposal tasks."""
        import copy
        from .provider_adapters import build_astra_request
        from .provider_images import ProviderImage
        from .report_store import StaleEvidenceGeneration, StaleReportPolicy, policy_revision

        spend = self.settings.provider_spend_policy
        adapter = self.adapter_factory()
        if not isinstance(spend, AstraSpendPolicy) or getattr(adapter, "billing_contract_id", None) != spend.adapter_id:
            raise ProviderDenied(["CLOUD_SPEND_BOUND_UNQUALIFIED"])
        approved_images = [(ProviderImage.model_validate_json(json.dumps(item)), payload) for item, payload in
            zip(images, image_payloads, strict=True)]
        prepared = build_astra_request(prompt, approved_images, approved_images=images,
            max_output_tokens=spend.max_output_tokens, task_type=task_type)
        request_id = "provider:" + hashlib.sha256(json.dumps([match_id, request_key]).encode()).hexdigest()
        # Proposal keys are deterministic, so an attempt that failed before dispatch
        # (no charge) must be retryable under the same key rather than dead forever.
        try:
            previous = self.budget_ledger.ledger.latest_attempt(request_id)
        except KeyError:
            previous = None
        retry_anchor = previous.attemptId if previous is not None and previous.status == "failed" \
            and self.budget_ledger.result(request_id) is None else None
        policy = self.resolve_policy(live_match, requested_provider="cloud", task_type=task_type,
            generation_id=generation_id, require_provider=True, prompt=prompt,
            request_id=request_id, source_identity=source_sha, adapter=adapter,
            retry_of_attempt_id=retry_anchor, visual_images=images, prepared_request=prepared)
        ticket = policy.ticket
        if ticket is None:
            raise ProviderDenied(["PROVIDER_RESERVATION_MISSING"])
        with self.storage.generations.guard(match_id, "publication"):
            stale_generation = self.storage.generations.resolve(match_id).generationId != generation_id
            stale_policy = policy_revision(self.storage.get_match(match_id), self.settings) != revision \
                or self.storage.source_sha256(match_id) != source_sha
            if stale_generation or stale_policy:
                current = self.budget_ledger.ledger.latest_attempt(request_id)
                self.budget_ledger.ledger.transition(current.attemptId, expected_revision=current.revision,
                    owner_id=ticket.owner_id, status="failed", noChargeReason="NO_DISPATCH_CONFIRMED",
                    error="STALE_EVIDENCE_GENERATION" if stale_generation else "STALE_REPORT_POLICY")
                if stale_generation:
                    raise StaleEvidenceGeneration("Evidence changed before dispatch")
                raise StaleReportPolicy("Policy or source changed before dispatch")
            original = self.budget_ledger.result(request_id)
            if original is not None:
                return {key: value for key, value in original.items() if key != "costSummary"}, request_id, policy, True
            self.budget_ledger.claim(ticket)
        try:
            with maintain_job_lease(self.budget_ledger.ledger, request_id, owner_id=ticket.owner_id):
                raw = adapter(task_type, frames, gateway_token=self._token,
                    provider="cloud", model_id=policy.model_id, deadline_seconds=policy.deadline_seconds,
                    prepared_request=copy.deepcopy(prepared),
                    execution_bound=copy.deepcopy(policy.execution_bound))
        except BaseException as exc:
            current = self.budget_ledger.ledger.latest_attempt(request_id)
            self.budget_ledger.ledger.transition(current.attemptId, expected_revision=current.revision,
                owner_id=ticket.owner_id,
                status="failed" if isinstance(exc, ProviderNotDispatched) else "outcome_unknown",
                noChargeReason="NO_DISPATCH_CONFIRMED" if isinstance(exc, ProviderNotDispatched) else None,
                error="NO_DISPATCH_CONFIRMED" if isinstance(exc, ProviderNotDispatched) else "PROVIDER_OUTCOME_UNKNOWN")
            raise
        current = self.budget_ledger.ledger.latest_attempt(request_id)
        self.budget_ledger.ledger.transition(current.attemptId, expected_revision=current.revision,
            owner_id=ticket.owner_id, status="complete")
        if isinstance(raw, ProviderResult):
            if raw.usage is not None:
                usage = raw.usage
                self.budget_ledger.ledger.reconcile_attempt(current.attemptId, provider_outcome="complete",
                    settled_cost=usage.total, billing_complete=usage.final,
                    receipt_id=request_id + ":" + usage.receipt_id)
            raw = raw.output
        return raw, request_id, policy, False

    def execute_event_proposal(self, match_id: str, *, body: dict[str, Any]) -> dict[str, Any]:
        """Reserve one visual review suggestion; never apply it to match truth."""
        from .provider_adapters import EventProposalDraft
        from .report_store import StaleEvidenceGeneration, StaleReportPolicy, policy_revision
        from .workbench.events import ModelEventProposal

        if not isinstance(body, dict) or set(body) != {"generationId", "imageManifestDigest", "requestId"} \
                or not isinstance(body["generationId"], str) \
                or not isinstance(body["imageManifestDigest"], str) \
                or not isinstance(body["requestId"], str) or not 1 <= len(body["requestId"]) <= 160:
            raise ValueError("Current generation, image manifest and bounded request ID required")
        with self.storage.generation_snapshot(match_id) as generation:
            generation_id = generation.generationId
            if body["generationId"] != generation_id:
                raise StaleEvidenceGeneration("Select the current generation before requesting an event proposal")
            package, inputs = self.build_evidence(match_id, generation_id, "event_proposal",
                image_manifest_digest=body["imageManifestDigest"])
        images = package.visual_images
        if not 1 <= len(images) <= 4 or len({item["sourceFrameId"] for item in images}) != len(images):
            raise ValueError("One to four distinct source images required")
        frame_times = {item["sourceFrameId"]: item["ptsSeconds"] for item in images}
        interval_start, interval_end = min(frame_times.values()), max(frame_times.values())
        if interval_end - interval_start > 10:
            raise ValueError("Event source images exceed ten seconds")
        source_sha = self.storage.source_sha256(match_id)
        if any(item["sourceSha256"] != source_sha for item in images):
            raise StaleEvidenceGeneration("Source changed before event dispatch")
        with self.storage.generations.guard(match_id, "publication"):
            if self.storage.generations.resolve(match_id).generationId != generation_id:
                raise StaleEvidenceGeneration("Evidence changed before dispatch")
            live_match = self.storage.get_match(match_id)
        revision = policy_revision(live_match, self.settings)
        prompt = ("Suggest at most one pass, turnover, recovery or shot visible in the ordered source images. "
                  "Use type none if the visual evidence is insufficient. Do not infer unseen motion, "
                  "player identity or a team from kit color alone. Choose a frameId from: "
                  + json.dumps([{"frameId": item["sourceFrameId"], "ptsSeconds": item["ptsSeconds"]}
                      for item in images], separators=(",", ":")))
        raw, request_id, policy, replay = self._dispatch_proposal(match_id, "event_proposal",
            generation_id=generation_id, source_sha=source_sha, revision=revision,
            live_match=live_match, prompt=prompt, request_key=body["requestId"],
            frames=inputs["frames"], images=images,
            image_payloads=inputs["visual_image_payloads"])
        if replay:
            return raw
        # The attempt is already complete and billed. An unusable answer is recorded
        # as "no suggestion" so the request key replays instead of failing forever.
        try:
            draft = EventProposalDraft.model_validate(raw)
        except ValueError:  # includes pydantic ValidationError
            draft = None
        with self.storage.generations.guard(match_id, "publication"):
            if self.storage.generations.resolve(match_id).generationId != generation_id:
                raise StaleEvidenceGeneration("Evidence changed during event proposal")
            if policy_revision(self.storage.get_match(match_id), self.settings) != revision \
                    or self.storage.source_sha256(match_id) != source_sha:
                raise StaleReportPolicy("Policy or source changed during event proposal")
            rejected = draft is None or (draft.type != "none" and draft.frameId not in frame_times)
            proposal = None
            if not rejected and draft.type != "none":
                proposal = ModelEventProposal(type=draft.type, frameId=draft.frameId,
                    timestamp=frame_times[draft.frameId], intervalStart=interval_start,
                    intervalEnd=interval_end, team=draft.team, description=draft.description,
                    modelId=policy.model_id, modelVersion=policy.model_id,
                    evidenceIds=[f"frame:{draft.frameId}"]).model_dump(mode="json")
            result = {"schemaVersion": "event_proposal_receipt_v1", "requestId": request_id,
                "matchId": match_id, "generationId": generation_id, "sourceSha256": source_sha,
                "modelId": policy.model_id, "modelVersion": policy.model_id, "proposal": proposal}
            if rejected:
                result["modelOutputRejected"] = True
            self.budget_ledger.save_result(request_id, result)
        return result

    def execute_query_proposal(self, match_id: str, *, body: dict[str, Any]) -> dict[str, Any]:
        """Map one bounded question to a validated filter and run the stored-event executor."""
        from .provider_adapters import QueryProposalDraft
        from .report_store import StaleEvidenceGeneration, StaleReportPolicy, policy_revision
        from .workbench.assistance import ALLOWED_EVENT_FAMILIES, validate_query_proposal

        if not isinstance(body, dict) or set(body) != {"generationId", "question", "requestId"} \
                or not isinstance(body["generationId"], str) \
                or not isinstance(body["question"], str) or not 0 < len(body["question"].strip()) <= 512 \
                or not isinstance(body["requestId"], str) or not 1 <= len(body["requestId"]) <= 160:
            raise ValueError("Current generation, bounded question and request ID required")
        with self.storage.generation_snapshot(match_id) as generation:
            generation_id = generation.generationId
            if body["generationId"] != generation_id:
                raise StaleEvidenceGeneration("Select the current generation before requesting a query proposal")
            source_sha = self.storage.source_sha256(match_id)
        with self.storage.generations.guard(match_id, "publication"):
            if self.storage.generations.resolve(match_id).generationId != generation_id:
                raise StaleEvidenceGeneration("Evidence changed before query dispatch")
            live_match = self.storage.get_match(match_id)
        revision = policy_revision(live_match, self.settings)
        prompt = ("Map the quoted analyst question to one supported event filter. Return unsupported if the "
                  "question asks for unavailable data or cannot be represented exactly. No SQL, code, invented "
                  "events or broadened filters. Allowed event families: "
                  + json.dumps(sorted(ALLOWED_EVENT_FAMILIES)) + ". Question: "
                  + json.dumps(body["question"].strip()))
        raw, request_id, policy, replay = self._dispatch_proposal(match_id, "query_proposal",
            generation_id=generation_id, source_sha=source_sha, revision=revision,
            live_match=live_match, prompt=prompt, request_key=body["requestId"], frames=[])
        if replay:
            return raw
        # The attempt is already complete and billed: record an unusable filter as an
        # unsupported answer so the same request key replays rather than failing forever.
        try:
            draft = QueryProposalDraft.model_validate(raw)
            query = validate_query_proposal({"matchId": match_id, "generationId": generation_id,
                "query": draft.query.model_dump(mode="json", exclude_none=True)},
                match_id=match_id, generation_id=generation_id) if draft.status == "query" else None
        except ValueError:  # includes pydantic ValidationError
            draft, query = None, None
        if draft is None:
            search = {"query": {"unanswerable": True, "reason": "invalid_model_output"},
                "interpreted": None, "unsupportedTerms": [], "results": [],
                "unknownLocationCount": 0, "coverageState": "unsupported"}
        elif query is not None:
            with self.storage.generation_snapshot(match_id, generation_id=generation_id):
                search = self.storage.query_match_events(match_id, query)
        else:
            search = {"query": {"unanswerable": True, "reason": draft.reason},
                "interpreted": None, "unsupportedTerms": [], "results": [],
                "unknownLocationCount": 0, "coverageState": "unsupported"}
        with self.storage.generations.guard(match_id, "publication"):
            if self.storage.generations.resolve(match_id).generationId != generation_id:
                raise StaleEvidenceGeneration("Evidence changed during query proposal")
            if policy_revision(self.storage.get_match(match_id), self.settings) != revision \
                    or self.storage.source_sha256(match_id) != source_sha:
                raise StaleReportPolicy("Policy or source changed during query proposal")
            result = {"schemaVersion": "query_proposal_receipt_v1", "requestId": request_id,
                "matchId": match_id, "generationId": generation_id, "sourceSha256": source_sha,
                "modelId": policy.model_id, "modelVersion": policy.model_id,
                "questionSha256": hashlib.sha256(body["question"].strip().encode()).hexdigest(),
                **search}
            self.budget_ledger.save_result(request_id, result)
        return result


def validate_output(raw: Any, package: ApprovedEvidencePackage) -> ValidatedOutput:
    from .report_contracts import check_output
    return ValidatedOutput(*check_output(raw, package))
