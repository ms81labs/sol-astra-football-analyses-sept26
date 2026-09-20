"""C04 final-review controls: exact admission and truthful provider publication."""
from decimal import Decimal
import pytest
from backend.tests.test_audit_v3_c04_costs import request, admit
from backend.tests.test_audit_v3_c04_providers import fake_policy, gateway_fixture, run
from backend.app.workbench.jobs import DurableJobLedger

pytestmark = pytest.mark.integration

@pytest.mark.parametrize("value", [Decimal("100000000000.000000000001")])
def test_admission_rejects_budget_that_would_be_silently_rounded(value):
    with pytest.raises(ValueError, match="MONEY_REPRESENTATION_UNSUPPORTED"):
        request(budget=value)


def test_utf8_input_bound_and_exact_nonzero_price_positive_control():
    policy = fake_policy(input_byte_price="0.001")
    bound = policy.bind(prompt="é⚽", task="report", model="test-model")
    assert bound["inputBytes"] == 5
    assert bound["maximumCost"] == "0.255"
    assert bound["reasoningEnabled"] is False


def test_high_precision_invoice_retained_exactly_even_above_budget(tmp_path):
    ledger = DurableJobLedger(tmp_path / "ledger.db")
    attempt = admit(ledger, request(budget=1))
    ledger.reconcile_attempt(attempt.attemptId, provider_outcome="complete",
        settled_cost="100000000000.000000000001", receipt_id="truthful-large-invoice")
    rows = ledger.charges_for(attempt.attemptId)
    assert [r["amount_exact"] for r in rows if r["kind"] == "settled"] == ["100000000000.000000000001"]
    assert "BUDGET_BREACH" in ledger.cost_for(attempt.requestId)["reasonCodes"]


def test_string_budget_is_not_silently_coerced_positive_control():
    with pytest.raises(ValueError):
        request(budget="0.25")


def test_stale_generation_does_not_lose_final_provider_invoice(tmp_path):
    from backend.app.provider_billing import ProviderResult, ProviderUsage
    from backend.app.review_service import ReviewService
    from backend.app.report_store import StaleEvidenceGeneration
    from backend.tests.test_audit_v3_c03_reports import _interprets
    calls=[]
    state={}
    def adapter(*args, **kw):
        calls.append(1)
        ReviewService(state["storage"]).configure(state["mid"], {"attackDirection":"right_to_left"})
        return ProviderResult(_interprets(*args, **kw), ProviderUsage("stale-invoice", ".12", True))
    storage,mid,gateway=gateway_fixture(tmp_path,adapter)
    state.update(storage=storage,mid=mid)
    generation=storage.current_generation(mid).generationId
    with pytest.raises(StaleEvidenceGeneration):
        run(gateway,mid)
    assert storage.current_generation(mid).generationId != generation
    requests=[r for r in storage.job_ledger.requests.values() if r.scope=="provider"]
    assert len(requests)==1 and calls==[1]
    cost=storage.job_ledger.cost_for(requests[0].requestId)
    assert cost["actualTotal"]==.12 and cost["billingComplete"] is True
    assert cost["attemptCount"]==1


def test_legacy_reservation_import_is_idempotent_after_store_relocation(tmp_path):
    import sqlite3
    from backend.app.provider_billing import ProviderBudgetLedger
    old=tmp_path/'old-provider.db'; main=tmp_path/'ledger.db'
    with sqlite3.connect(old) as c:
        c.execute('CREATE TABLE provider_reservations(id TEXT PRIMARY KEY,match_id TEXT,task_type TEXT,amount REAL)')
        c.execute('INSERT INTO provider_reservations VALUES (?,?,?,?)',('stable-legacy-id','match','report',.3))
    ProviderBudgetLedger(main,1,legacy_path=old)
    moved=tmp_path/'moved-provider.db';old.rename(moved)
    ledger=ProviderBudgetLedger(main,1,legacy_path=moved).ledger
    assert ledger.cost_summary()['attemptCount']==1
    assert ledger.cost_summary()['unsettledTotal']==.3
    assert ledger.cost_summary()['actualTotal'] is None


def test_legacy_receipt_reuse_with_changed_amount_is_a_conflict(tmp_path):
    import sqlite3
    from backend.app.provider_billing import ProviderBudgetLedger
    from backend.app.workbench.errors import IdempotencyConflict
    old=tmp_path/'old-provider.db';main=tmp_path/'ledger.db'
    with sqlite3.connect(old) as c:
        c.execute('CREATE TABLE provider_reservations(id TEXT PRIMARY KEY,match_id TEXT,task_type TEXT,amount REAL)')
        c.execute('INSERT INTO provider_reservations VALUES (?,?,?,?)',('stable-legacy-id','match','report',.3))
    ProviderBudgetLedger(main,1,legacy_path=old)
    with sqlite3.connect(old) as c:c.execute('UPDATE provider_reservations SET amount=.4')
    with pytest.raises(IdempotencyConflict):ProviderBudgetLedger(main,1,legacy_path=old)
    assert DurableJobLedger(main).cost_summary()['unsettledTotal']==.3
