"""Provider billing uses the existing transactional ledger, never a second balance.

No production adapter is currently qualified for this bounded contract. The explicit
byte/token policy is exercised by injected synthetic adapters; production dispatch
is refused until an adapter can enforce every declared billable component.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .workbench.errors import BudgetExhausted, IdempotencyConflict, ReconciliationRequired
from .workbench.jobs import DurableJobLedger, JobAttempt, JobRequest
from .workbench.money import admission_money, money, text, total


@dataclass(frozen=True)
class ProviderSpendPolicy:
    policy_id: str
    adapter_id: str
    model_id: str
    task_types: tuple[str, ...]
    currency: str
    max_input_bytes: int
    max_output_tokens: int
    input_byte_price: str
    output_token_price: str
    billable_components: tuple[str, ...] = ('input_bytes', 'output_tokens')

    def __post_init__(self) -> None:
        if self.billable_components != ('input_bytes', 'output_tokens'):
            raise ValueError('UNSUPPORTED_BILLABLE_COMPONENT')
        if not all(isinstance(v, str) and v for v in (self.policy_id, self.adapter_id, self.model_id)):
            raise ValueError('policy, adapter and model identities are required')
        if not isinstance(self.task_types, tuple) or not self.task_types or not all(isinstance(v, str) and v for v in self.task_types):
            raise ValueError('explicit task identities required')
        if len(self.currency) != 3 or not self.currency.isascii() or not self.currency.isupper() or not self.currency.isalpha():
            raise ValueError('invalid currency')
        if type(self.max_input_bytes) is not int or not 0 < self.max_input_bytes <= 16 * 1024**2:
            raise ValueError('invalid input bound')
        if type(self.max_output_tokens) is not int or not 0 < self.max_output_tokens <= 100000:
            raise ValueError('invalid output bound')
        money(self.input_byte_price)
        money(self.output_token_price)

    def bind(self, *, prompt: str, task: str, model: str) -> dict[str, Any]:
        if task not in self.task_types or model != self.model_id:
            raise ValueError('MODEL_TASK_BOUND_MISMATCH')
        encoded = prompt.encode('utf-8')
        if len(encoded) > self.max_input_bytes:
            raise ValueError('INPUT_BOUND_EXCEEDED')
        maximum = total((len(encoded) * money(self.input_byte_price),
                         self.max_output_tokens * money(self.output_token_price)))
        money(maximum)
        return {
            'schemaVersion': 1, 'policyId': self.policy_id, 'adapterId': self.adapter_id,
            'modelId': model, 'taskType': task, 'currency': self.currency,
            'inputBytes': len(encoded), 'maxInputBytes': self.max_input_bytes,
            'promptSha256': hashlib.sha256(encoded).hexdigest(),
            'maxOutputTokens': self.max_output_tokens, 'toolsEnabled': False,
            'reasoningEnabled': False, 'billableComponents': list(self.billable_components),
            'inputBytePrice': text(money(self.input_byte_price)),
            'outputTokenPrice': text(money(self.output_token_price)), 'maximumCost': text(maximum),
        }


@dataclass(frozen=True)
class ProviderUsage:
    receipt_id: str
    total: str
    final: bool

    def __post_init__(self) -> None:
        if not isinstance(self.receipt_id, str) or not self.receipt_id or len(self.receipt_id) > 512:
            raise ValueError('billing receipt identity required')
        if type(self.final) is not bool:
            raise ValueError('billing finality must be explicit')
        money(self.total)


@dataclass(frozen=True)
class ProviderResult:
    output: Any
    usage: ProviderUsage | None = None


class ProviderNotDispatched(ValueError):
    """Trusted adapter proof that validation failed before any transport submission."""


@dataclass(frozen=True)
class ProviderTicket:
    request: JobRequest
    attempt: JobAttempt
    owner_id: str


class ProviderBudgetLedger:
    """Compatibility facade; request/attempt/money authority is DurableJobLedger."""

    def __init__(self, path: Path, limit: float, *, legacy_path: Path | None = None) -> None:
        self.path = Path(path)
        self.limit = money(limit)
        self.ledger = DurableJobLedger(self.path)
        self._import_legacy(legacy_path or self.path)

    def _import_legacy(self, source: Path) -> None:
        if not source.is_file():
            return
        # Read the historical file without editing any reservation or manufacturing zero.
        with sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True) as connection:
            if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='provider_reservations'").fetchone():
                return
            rows = connection.execute('SELECT id,match_id,task_type,amount FROM provider_reservations ORDER BY id').fetchall()
        for ident, match, task, amount in rows:
            # A database move must not turn the same historical reservation into
            # another attempt. The old ledger assigned a stable reservation ID.
            key = 'legacy-provider:' + hashlib.sha256(str(ident).encode()).hexdigest()
            if self.ledger.has_request(key):
                existing = self.ledger.request(key)
                previous = existing.executionBound or {}
                if (existing.scope != 'provider' or existing.matchId != match
                        or existing.providerTask != task or previous.get('rowId') != ident
                        or money(previous.get('amount')) != money(amount)):
                    raise IdempotencyConflict(key)
                continue
            bound = {'legacySource': str(source.resolve()), 'rowId': ident, 'amount': amount,
                     'qualification': 'unknown'}
            ticket = self._admit(match, task, money(amount), key, '', '', bound, money(amount),
                                 'USD', enforce_limit=False)
            latest = self.ledger.latest_attempt(key)
            self.ledger.transition(latest.attemptId, expected_revision=latest.revision,
                owner_id=ticket.owner_id, status='outcome_unknown', error='LEGACY_PROVIDER_OUTCOME_UNKNOWN')

    def _admit(self, match: str, task: str, amount, request_id: str, source: str,
               model: str, bound: dict | None, budget, currency: str, *, enforce_limit: bool = True, retry_of_attempt_id: str | None = None) -> ProviderTicket:
        request = JobRequest(requestId=request_id, matchId=match,
            sourceSha256=source or hashlib.sha256(json.dumps([match, task]).encode()).hexdigest(),
            intervalStart=0, intervalEnd=0, temporalPolicy='provider-request-v2',
            decoderVersion='not-applicable', modelHash=model or 'legacy-unknown',
            outputSchema='provider-result-v2', budget=float(admission_money(budget)), authorisedLocation='cloud',
            currency=currency, scope='provider', providerTask=task, executionBound=bound)
        owner = 'provider:' + str(uuid.uuid4())
        attempt = self.ledger.admit(request, mode='retry' if retry_of_attempt_id is not None else 'submit',
            owner_id=owner, lease_seconds=120, retry_of_attempt_id=retry_of_attempt_id,
            reservation=admission_money(amount), group_limit=self.limit if enforce_limit else None)
        return ProviderTicket(request, attempt, owner)

    def admit(self, *, match_id: str, task_type: str, request_id: str, source_identity: str,
              execution_bound: dict, authorised_budget: float,
              retry_of_attempt_id: str | None = None) -> ProviderTicket | None:
        amount = money(execution_bound['maximumCost'])
        try:
            return self._admit(match_id, task_type, amount, request_id, source_identity,
                execution_bound['modelId'], execution_bound, money(authorised_budget), execution_bound['currency'],
                retry_of_attempt_id=retry_of_attempt_id)
        except BudgetExhausted:
            return None

    def reserve(self, *, match_id: str, task_type: str, amount: float) -> float | None:
        """Historical API: reserve capacity only; this never authorises dispatch."""
        try:
            exact = money(amount)
            if exact <= 0:
                return None
            self._admit(match_id, task_type, exact, 'provider:' + str(uuid.uuid4()), '', '',
                        None, exact, 'USD')
        except (ValueError, BudgetExhausted):
            return None
        return float(exact)

    def reservations(self) -> list[dict[str, object]]:
        with self.ledger._connect() as connection:
            connection.execute('BEGIN')
            result = []
            for row in connection.execute('SELECT payload_json FROM job_requests ORDER BY rowid'):
                req = JobRequest.model_validate_json(row['payload_json'])
                if req.scope != 'provider':
                    continue
                for attempt_row in connection.execute('SELECT payload_json FROM job_attempts WHERE request_id=? ORDER BY sequence', (req.requestId,)):
                    attempt = JobAttempt.model_validate_json(attempt_row['payload_json'])
                    result.append({'matchId': req.matchId, 'taskType': req.providerTask,
                                   'amount': attempt.reservedCost})
            return result

    def claim(self, ticket: ProviderTicket) -> JobAttempt:
        if not self.ledger.claim_dispatch(ticket.request.requestId, owner_id=ticket.owner_id, phase="running"):
            raise ReconciliationRequired('provider request already executed or cancellation requested')
        return self.ledger.latest_attempt(ticket.request.requestId)

    def result(self, request_id: str) -> dict | None:
        with self.ledger._connect() as connection:
            row = connection.execute('SELECT response_json FROM provider_results WHERE request_id=?', (request_id,)).fetchone()
        if row is None:
            return None
        return {**json.loads(row['response_json']), 'costSummary': self.ledger.cost_for(request_id)}

    def save_result(self, request_id: str, result: dict) -> None:
        payload = json.dumps(result, allow_nan=False, sort_keys=True)
        with self.ledger._transaction() as connection:
            connection.execute('INSERT INTO provider_results VALUES (?,?) ON CONFLICT(request_id) DO NOTHING', (request_id, payload))
