"""C04 R07: billing evidence, not execution status, determines final cost.

Synthetic ledger/provider fixtures only. Never dispatch a paid worker/provider.
"""
from pathlib import Path

import pytest

from backend.app.provider_gateway import ProviderBudgetLedger
from backend.app.workbench.jobs import DurableJobLedger, JobRequest

pytestmark = pytest.mark.integration


def request(key="c04", budget=1.0, location="daytona", **extra):
    return JobRequest(requestId=key, matchId="match", sourceSha256="a" * 64,
        intervalStart=0, intervalEnd=1, temporalPolicy="source_global_grid",
        decoderVersion="opencv", modelHash="fixture", outputSchema="evidence_v1",
        budget=budget, authorisedLocation=location, **extra)


def admit(ledger, req=None):
    return ledger.admit(req or request(), mode="submit", owner_id="worker", lease_seconds=60)


def change(ledger, attempt, status, **updates):
    current = ledger.latest_attempt(attempt.requestId)
    return ledger.transition(current.attemptId, expected_revision=current.revision,
                             owner_id="worker", status=status, **updates)


def test_v3t29_queued_receipt_is_not_a_final_zero(tmp_path):
    ledger = DurableJobLedger(tmp_path / "jobs.db")
    attempt = admit(ledger)
    assert ledger.receipt(attempt.requestId).actualTotal is None


def test_v3t29_timeout_cost_views_do_not_claim_zero(tmp_path):
    ledger = DurableJobLedger(tmp_path / "jobs.db")
    attempt = admit(ledger)
    ledger.timeout_before_response(attempt.requestId, owner_id="worker")
    assert ledger.cost_for(attempt.requestId)["actualTotal"] is None
    assert ledger.cost_summary()["actualTotal"] is None
    assert ledger.receipt(attempt.requestId).actualTotal is None


def test_v3t30_partial_invoice_plus_unknown_is_not_final(tmp_path):
    ledger = DurableJobLedger(tmp_path / "jobs.db")
    attempt = admit(ledger)
    ledger.record_charge(attempt.attemptId, kind="settled", amount=0.25)
    ledger.timeout_before_response(attempt.requestId, owner_id="worker")
    assert ledger.cost_for(attempt.requestId)["actualTotal"] is None
    assert ledger.receipt(attempt.requestId).settledTotal == 0.25


def test_v3t34_remote_completion_without_invoice_keeps_exposure(tmp_path):
    ledger = DurableJobLedger(tmp_path / "jobs.db")
    attempt = admit(ledger)
    change(ledger, attempt, "complete")
    assert ledger.receipt(attempt.requestId).actualTotal is None
    assert ledger.cost_for(attempt.requestId)["reservedTotal"] == 1.0


def test_v3t31_actual_overrun_is_recorded_not_rejected(tmp_path):
    ledger = DurableJobLedger(tmp_path / "jobs.db")
    attempt = admit(ledger)
    change(ledger, attempt, "complete", actualCost=1.25)
    assert ledger.receipt(attempt.requestId).actualTotal == 1.25


def test_v3t29_attempt_count_is_not_reservation_row_count(tmp_path):
    ledger = DurableJobLedger(tmp_path / "jobs.db")
    attempt = admit(ledger)
    ledger.record_charge(attempt.attemptId, kind="reserved", amount=0.0)
    assert ledger.cost_for(attempt.requestId)["attempts"] == 1


def test_v3t31_decimal_provider_admission_does_not_lose_capacity(tmp_path):
    ledger = ProviderBudgetLedger(tmp_path / "providers.db", 0.3)
    reservations = [ledger.reserve(match_id="match", task_type="tactical_report", amount=0.1)
                    for _ in range(3)]
    assert reservations == [0.1, 0.1, 0.1]
    assert ledger.reserve(match_id="match", task_type="tactical_report", amount=0.1) is None


def test_v3t34_reconciliation_without_charge_does_not_invent_zero(tmp_path):
    ledger = DurableJobLedger(tmp_path / "jobs.db")
    attempt = admit(ledger)
    ledger.timeout_before_response(attempt.requestId, owner_id="worker")
    ledger.reconcile_attempt(attempt.attemptId, provider_outcome="complete", settled_cost=None)
    assert ledger.receipt(attempt.requestId).actualTotal is None


def test_v3t30_explicit_final_zero_positive_control(tmp_path):
    ledger = DurableJobLedger(tmp_path / "jobs.db")
    attempt = admit(ledger)
    change(ledger, attempt, "complete", actualCost=0.0)
    assert ledger.receipt(attempt.requestId).actualTotal == 0.0


def test_v3t32_idempotent_completed_submit_positive_control(tmp_path):
    ledger = DurableJobLedger(tmp_path / "jobs.db")
    req = request()
    attempt = admit(ledger, req)
    change(ledger, attempt, "complete", actualCost=0.2)
    assert admit(ledger, req).attemptId == attempt.attemptId
    assert ledger.receipt(req.requestId).attemptCount == 1


def test_v3t29_same_contract_in_receipt_job_and_cost_views(tmp_path):
    from backend.app.workbench.jobs import attach_durable_job_view
    ledger = DurableJobLedger(tmp_path / "jobs.db")
    attempt = admit(ledger)
    for phase in ("submitted", "running", "outcome_unknown"):
        if phase != "submitted":
            change(ledger, attempt, phase)
        costs = ledger.cost_for(attempt.requestId)
        receipt = ledger.receipt(attempt.requestId).costSummary.model_dump(mode="json")
        job = attach_durable_job_view({"id": attempt.requestId}, ledger)
        assert {k: costs[k] for k in receipt} == receipt == job["costSummary"]
        assert costs["reservedTotal"] == costs["outstandingReserved"] + costs["unsettledTotal"]
        assert costs["actualTotal"] is None and not costs["billingComplete"]
    reopened = DurableJobLedger(ledger.db_path)
    assert reopened.cost_for(attempt.requestId) == costs


def test_v3t30_currencies_are_separate_not_added(tmp_path):
    ledger = DurableJobLedger(tmp_path / "jobs.db")
    for currency in ("USD", "EUR"):
        attempt = admit(ledger, request(currency, currency=currency))
        change(ledger, attempt, "complete", actualCost=0.5)
    result = ledger.cost_summary()
    assert result["actualTotal"] is None and result["currency"] is None
    assert result["reasonCodes"] == ["MIXED_CURRENCIES"]
    assert result["byCurrency"]["USD"]["actualTotal"] == 0.5
    assert result["byCurrency"]["EUR"]["actualTotal"] == 0.5


def test_v3t31_partial_then_final_invoice_replay_is_idempotent(tmp_path):
    ledger = DurableJobLedger(tmp_path / "jobs.db")
    attempt = admit(ledger)
    ledger.timeout_before_response(attempt.requestId, owner_id="worker")
    ledger.reconcile_attempt(attempt.attemptId, provider_outcome="complete", settled_cost=0.2,
                             billing_complete=False, receipt_id="partial")
    cost = ledger.cost_for(attempt.requestId)
    assert cost["settledTotal"] == 0.2 and cost["unsettledTotal"] == 0.8
    assert cost["actualTotal"] is None and cost["unsettledAttemptCount"] == 1
    ledger.reconcile_attempt(attempt.attemptId, provider_outcome="complete", settled_cost=0.3,
                             receipt_id="final")
    charges = ledger.charges_for(attempt.attemptId)
    ledger.reconcile_attempt(attempt.attemptId, provider_outcome="complete", settled_cost=0.3,
                             receipt_id="final")
    assert ledger.charges_for(attempt.attemptId) == charges
    assert ledger.cost_for(attempt.requestId)["actualTotal"] == 0.3


def test_v3t34_old_invoice_replay_cannot_clear_new_uncertainty(tmp_path):
    ledger = DurableJobLedger(tmp_path / "jobs.db")
    attempt = admit(ledger)
    ledger.reconcile_attempt(attempt.attemptId, provider_outcome="complete", settled_cost=0.2,
                             receipt_id="invoice-v1")
    change(ledger, attempt, "outcome_unknown")
    ledger.reconcile_attempt(attempt.attemptId, provider_outcome="complete", settled_cost=0.2,
                             receipt_id="invoice-v1")
    current = ledger.cost_for(attempt.requestId)
    assert current["actualTotal"] is None and current["settledTotal"] == 0.2
    assert current["unsettledTotal"] == 0.8 and not current["billingComplete"]


def test_v3t31_partial_invoice_event_replay_does_not_add_twice(tmp_path):
    ledger = DurableJobLedger(tmp_path / "jobs.db")
    attempt = admit(ledger)
    ledger.record_charge(attempt.attemptId, kind="settled", amount=0.2, evidence_id="partial-event")
    before = ledger.charges_for(attempt.attemptId)
    ledger.record_charge(attempt.attemptId, kind="settled", amount=0.2, evidence_id="partial-event")
    assert ledger.charges_for(attempt.attemptId) == before
    assert ledger.receipt(attempt.requestId).settledTotal == 0.2


def test_v3t34_zero_exposure_does_not_erase_uncertain_attempt(tmp_path):
    from backend.app.workbench.errors import ReconciliationRequired
    ledger = DurableJobLedger(tmp_path / "jobs.db")
    attempt = admit(ledger, request(budget=0))
    change(ledger, attempt, "outcome_unknown")
    cost = ledger.cost_for(attempt.requestId)
    assert cost["actualTotal"] is None and cost["unsettledAttemptCount"] == 1
    assert "UNBOUNDED_EXPOSURE" in cost["reasonCodes"]
    with pytest.raises(ReconciliationRequired):
        ledger.retry(attempt.requestId)


def test_v3t31_overrun_blocks_new_paid_attempt(tmp_path):
    from backend.app.workbench.errors import BudgetExhausted
    ledger = DurableJobLedger(tmp_path / "jobs.db")
    attempt = admit(ledger)
    change(ledger, attempt, "failed", actualCost=1.2)
    assert "BUDGET_BREACH" in ledger.cost_for(attempt.requestId)["reasonCodes"]
    with pytest.raises(BudgetExhausted):
        ledger.retry(attempt.requestId)
    assert ledger.cost_for(attempt.requestId)["actualTotal"] == 1.2


@pytest.mark.parametrize("value", [True, False, float("nan"), float("inf"), -0.01])
def test_v3t31_invalid_invoice_never_mutates_ledger(tmp_path, value):
    ledger = DurableJobLedger(tmp_path / "jobs.db")
    attempt = admit(ledger)
    before = ledger.charges_for(attempt.attemptId)
    with pytest.raises(ValueError):
        ledger.reconcile_attempt(attempt.attemptId, provider_outcome="complete", settled_cost=value)
    assert ledger.charges_for(attempt.attemptId) == before
    assert ledger.cost_for(attempt.requestId)["actualTotal"] is None


def test_v3t34_cancel_and_cleanup_do_not_prove_remote_no_charge(tmp_path):
    ledger = DurableJobLedger(tmp_path / "jobs.db")
    attempt = admit(ledger)
    ledger.request_cancel(attempt.requestId)
    ledger.confirm_termination(attempt.requestId, owner_id="worker")
    ledger.confirm_cleanup(attempt.requestId, owner_id="worker", ok=True)
    cost = ledger.cost_for(attempt.requestId)
    assert cost["actualTotal"] is None and cost["unsettledAttemptCount"] == 1
    assert cost["unsettledTotal"] == 1


def test_v3t34_wrong_owner_cannot_write_termination_evidence(tmp_path):
    import sqlite3
    from backend.app.workbench.errors import NotOwner
    ledger = DurableJobLedger(tmp_path / "jobs.db")
    attempt = admit(ledger)
    ledger.request_cancel(attempt.requestId)
    with pytest.raises(NotOwner):
        ledger.confirm_termination(attempt.requestId, owner_id="intruder")
    with sqlite3.connect(ledger.db_path) as db:
        assert db.execute("SELECT termination_confirmed_at FROM job_cancels").fetchone()[0] is None
    assert ledger.cost_for(attempt.requestId)["actualTotal"] is None


def test_v3t30_legacy_released_reservation_without_invoice_stays_unknown(tmp_path):
    import sqlite3, json
    path = tmp_path / "old.db"
    ledger = DurableJobLedger(path)
    attempt = admit(ledger)
    # Recreate a pre-C04 terminal payload whose old writer released all budget.
    with sqlite3.connect(path) as db:
        payload = attempt.model_dump(mode="json")
        payload.update(status="complete", actualCost=None)
        db.execute("UPDATE job_attempts SET status='complete',payload_json=?", (json.dumps(payload),))
        db.execute("INSERT INTO job_charges VALUES ('old-release',?,?, 'released',1,'old',NULL)",
                   (attempt.requestId, attempt.attemptId))
        db.execute("DELETE FROM job_billing_migrations")
        source = db.execute("SELECT * FROM job_charges ORDER BY charge_id").fetchall()
    migrated = DurableJobLedger(path)
    assert migrated.cost_for(attempt.requestId)["actualTotal"] is None
    assert migrated.cost_for(attempt.requestId)["unsettledTotal"] == 1
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT * FROM job_charges ORDER BY charge_id").fetchall() == source
    assert DurableJobLedger(path).cost_for(attempt.requestId) == migrated.cost_for(attempt.requestId)


def test_v3t31_changed_increment_under_same_receipt_is_refused(tmp_path):
    from backend.app.workbench.errors import IdempotencyConflict
    ledger = DurableJobLedger(tmp_path / 'jobs.db')
    attempt = admit(ledger)
    ledger.record_charge(attempt.attemptId, kind='settled', amount=.2, evidence_id='part')
    with pytest.raises(IdempotencyConflict):
        ledger.record_charge(attempt.attemptId, kind='settled', amount=.3, evidence_id='part')
    assert ledger.cost_for(attempt.requestId)['settledTotal'] == .2


def test_v3t29_attempt_view_does_not_keep_obsolete_final_invoice(tmp_path):
    ledger = DurableJobLedger(tmp_path / 'jobs.db')
    attempt = admit(ledger)
    change(ledger, attempt, 'complete', actualCost=.2)
    ledger.record_charge(attempt.attemptId, kind='settled', amount=.1, evidence_id='later-partial')
    assert ledger.latest_attempt(attempt.requestId).actualCost is None
    assert ledger.attempts[attempt.requestId][0].actualCost is None
    assert ledger.receipt(attempt.requestId).settledTotal == .3


def test_v3t33_real_cloud_adapter_is_disabled_without_qualified_billing(monkeypatch):
    from backend.app.provider_adapters import execute_cloud
    import httpx
    monkeypatch.setenv('OPENROUTER_API_KEY', 'must-not-be-used')
    monkeypatch.setattr(httpx.Client, 'post', lambda *a, **k: pytest.fail('unqualified network dispatch'))
    with pytest.raises(ValueError, match='CLOUD_SPEND_BOUND_UNQUALIFIED'):
        execute_cloud('prompt', 'tactical_report', lambda *a: {})


def test_v3t32_job_start_claims_dispatch_once(tmp_path, monkeypatch):
    from backend.app.jobs import JobRunner
    from backend.app.settings import ProcessingSettings
    runner = JobRunner(tmp_path, settings=ProcessingSettings(), run_jobs_inline=False)
    runner.admit('job-once', match_id='match', source_sha256='a' * 64, namespace='development')
    calls = []
    monkeypatch.setattr(runner, '_dispatch', lambda job: calls.append(job))
    runner.start('job-once')
    runner.start('job-once')
    assert calls == ['job-once']


def test_v3t34_cancel_before_job_dispatch_never_launches(tmp_path, monkeypatch):
    from backend.app.jobs import JobRunner
    from backend.app.settings import ProcessingSettings
    runner = JobRunner(tmp_path, settings=ProcessingSettings(), run_jobs_inline=False)
    runner.admit('cancel-before', match_id='match', source_sha256='a' * 64, namespace='development')
    runner.ledger.request_cancel('cancel-before')
    monkeypatch.setattr(runner, '_dispatch', lambda job: pytest.fail('cancelled work dispatched'))
    runner.start('cancel-before')
    assert runner.ledger.receipt('cancel-before').actualTotal == 0


def test_v3t32_repeated_unsettled_event_keeps_raw_history_unchanged(tmp_path):
    ledger = DurableJobLedger(tmp_path / 'jobs.db')
    attempt = admit(ledger)
    ledger.record_charge(attempt.attemptId, kind='unsettled', amount=.2, evidence_id='unknown')
    before = ledger.charges_for(attempt.attemptId)
    ledger.record_charge(attempt.attemptId, kind='unsettled', amount=.2, evidence_id='unknown')
    assert ledger.charges_for(attempt.attemptId) == before


def test_v3t34_late_termination_ack_preserves_final_invoice(tmp_path):
    ledger = DurableJobLedger(tmp_path/'jobs.db')
    attempt=admit(ledger)
    ledger.request_cancel(attempt.requestId)
    ledger.reconcile_attempt(attempt.attemptId,provider_outcome='complete',settled_cost=.17,receipt_id='invoice')
    ledger.confirm_termination(attempt.requestId,owner_id='worker',cost_known=False)
    ledger.confirm_cleanup(attempt.requestId,owner_id='worker',ok=True)
    assert ledger.cost_for(attempt.requestId)['actualTotal']==.17


def test_v3t31_unreconciled_breach_blocks_new_paid_work_but_not_local(tmp_path):
    from backend.app.workbench.errors import BudgetExhausted
    ledger = DurableJobLedger(tmp_path/'jobs.db')
    attempt = admit(ledger)
    change(ledger,attempt,'complete',actualCost=1.25)
    with pytest.raises(BudgetExhausted): admit(ledger,request('new-paid'))
    assert admit(ledger,request('local-work',location='local',budget=0)).status=='submitted'


def test_v3t30_legacy_remote_zero_without_no_charge_evidence_stays_unknown(tmp_path):
    import sqlite3, json
    path=tmp_path/'old.db';ledger=DurableJobLedger(path);attempt=admit(ledger)
    with sqlite3.connect(path) as db:
        payload=attempt.model_dump(mode='json')
        payload.update(status='failed',actualCost=0,reconciled=True)
        db.execute("UPDATE job_attempts SET status='failed',reconciled=1,payload_json=?", (json.dumps(payload),))
        db.execute("DELETE FROM job_billing_migrations")
    reopened=DurableJobLedger(path)
    assert reopened.cost_for(attempt.requestId)['actualTotal'] is None
    assert reopened.cost_for(attempt.requestId)['unsettledTotal']==1


def test_v3t32_retry_anchor_replays_its_child_even_after_later_failure(tmp_path):
    from backend.app.workbench.errors import ReconciliationRequired
    ledger=DurableJobLedger(tmp_path/'jobs.db');first=admit(ledger)
    change(ledger,first,'failed',actualCost=.1)
    second=ledger.admit(request(),mode='retry',owner_id='worker',lease_seconds=60,retry_of_attempt_id=first.attemptId)
    change(ledger,second,'failed',actualCost=.1)
    replay=ledger.admit(request(),mode='retry',owner_id='worker',lease_seconds=60,retry_of_attempt_id=first.attemptId)
    assert replay.attemptId==second.attemptId
    assert ledger.receipt(first.requestId).attemptCount==2
    with pytest.raises(ReconciliationRequired):
        ledger.admit(request(),mode='retry',owner_id='worker',lease_seconds=60,retry_of_attempt_id='foreign')


def test_v3t29_job_view_uses_its_receipt_snapshot_not_a_later_termination(tmp_path,monkeypatch):
    from backend.app.workbench.jobs import attach_durable_job_view
    ledger=DurableJobLedger(tmp_path/'jobs.db');attempt=admit(ledger)
    change(ledger,attempt,'running')
    original=ledger.receipt
    def receipt_then_finish(key):
        receipt=original(key)
        change(ledger,attempt,'complete',actualCost=.1)
        return receipt
    monkeypatch.setattr(ledger,'receipt',receipt_then_finish)
    view=attach_durable_job_view({'id':attempt.requestId,'status':'running'},ledger)
    assert view['durablePhase']=='running'
    assert view['terminated'] is False
    assert view['costSummary']['actualTotal'] is None
