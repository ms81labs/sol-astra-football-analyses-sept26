"""C04 fake bounded adapters test accounting without any provider network access."""
import hashlib
from dataclasses import replace
import pytest
from backend.app.settings import ProcessingSettings
from backend.app.provider_gateway import ProviderGateway, ProviderBudgetLedger, ProviderDenied
from backend.tests.test_audit_v3_c03_reports import _store, _interprets

pytestmark = pytest.mark.integration


def fake_policy(**changes):
    from backend.app.provider_billing import ProviderSpendPolicy
    base = dict(policy_id='test-price-v1', adapter_id='synthetic-byte-token-v1', model_id='test-model',
                task_types=('tactical_report', 'report'), currency='USD', max_input_bytes=1000000,
                max_output_tokens=25, input_byte_price='0', output_token_price='0.01')
    return ProviderSpendPolicy(**{**base, **changes})


def gateway_fixture(tmp_path, adapter, *, policy=True, budget=1.0):
    storage, mid = _store(tmp_path)
    config = storage.get_match(mid).config.model_copy(deep=True)
    config.rights.cloudPermission = True
    config.rights.processingScope = 'local_plus_burst'
    storage.update_match_config(mid, config)
    adapter.billing_contract_id = 'synthetic-byte-token-v1'
    settings = ProcessingSettings(cloud_provider_enabled=True, cloud_provider_api_key='test-only',
        allowed_model_ids=('test-model',), cloud_model_id='test-model',
        provider_call_reservation=.25, provider_budget_limit=budget,
        provider_spend_policy=fake_policy() if policy else None)
    gateway = ProviderGateway(storage, settings, adapter_factory=lambda: adapter,
        budget_ledger=ProviderBudgetLedger(storage.job_ledger.db_path, budget))
    return storage, mid, gateway


def run(gateway, mid, key='logical-report'):
    return gateway.execute(mid, 'tactical_report', requested_provider='cloud',
                           body={'requireProvider': True, 'requestId': key})


def test_v3t33_bound_reaches_actual_adapter_and_final_usage_is_retained(tmp_path):
    from backend.app.provider_billing import ProviderResult, ProviderUsage
    calls = []
    def adapter(*args, **kw):
        calls.append(kw)
        bound = kw['execution_bound']
        assert len(kw['prepared_prompt'].encode()) == bound['inputBytes']
        assert hashlib.sha256(kw['prepared_prompt'].encode()).hexdigest() == bound['promptSha256']
        assert bound['maxOutputTokens'] == 25 and bound['toolsEnabled'] is False
        return ProviderResult(_interprets(*args, **kw), ProviderUsage('receipt-1', '.12', True))
    storage, mid, gateway = gateway_fixture(tmp_path, adapter)
    result = run(gateway, mid)
    assert result['costSummary']['actualTotal'] == .12
    assert result['costSummary']['billingComplete'] is True
    assert storage.job_ledger.cost_summary()['actualTotal'] == .12
    repeated = run(gateway, mid)
    assert repeated['reportId'] == result['reportId'] and len(calls) == 1


def test_v3t33_unknown_price_refused_before_reservation_or_dispatch(tmp_path):
    def adapter(*a, **k): pytest.fail('no qualified pricing')
    storage, mid, gateway = gateway_fixture(tmp_path, adapter, policy=False)
    with pytest.raises(ProviderDenied, match='CLOUD_SPEND_BOUND_UNQUALIFIED'):
        run(gateway, mid)
    assert gateway.budget_ledger.reservations() == []


def test_rights_revoked_after_reservation_prevents_provider_dispatch(tmp_path, monkeypatch):
    from backend.app.report_store import StaleReportPolicy
    calls = []
    def adapter(*args, **kwargs):
        calls.append(1)
        return _interprets(*args, **kwargs)
    storage, mid, gateway = gateway_fixture(tmp_path, adapter)
    resolve = gateway.resolve_policy
    def revoke_after_reservation(match, **kwargs):
        policy = resolve(match, **kwargs)
        config = storage.get_match(mid).config.model_copy(deep=True)
        config.rights.cloudPermission = False
        storage.update_match_config(mid, config)
        return policy
    monkeypatch.setattr(gateway, 'resolve_policy', revoke_after_reservation)
    with pytest.raises(StaleReportPolicy):
        run(gateway, mid)
    assert calls == []
    cost = storage.job_ledger.cost_summary()
    assert cost['unsettledAttemptCount'] == 0


@pytest.mark.parametrize('mode', ['timeout', 'cancel', 'malformed'])
def test_v3t34_possible_bill_survives_failed_execution(tmp_path, mode):
    import asyncio
    def adapter(*a, **kw):
        if mode == 'timeout': raise TimeoutError('after dispatch')
        if mode == 'cancel': raise asyncio.CancelledError('after dispatch')
        return object()
    storage, mid, gateway = gateway_fixture(tmp_path, adapter)
    if mode == 'malformed':
        result = run(gateway, mid)
        assert result['costSummary']['actualTotal'] is None
    else:
        with pytest.raises((TimeoutError, asyncio.CancelledError)):
            run(gateway, mid)
    cost = storage.job_ledger.cost_summary()
    assert cost['actualTotal'] is None and cost['unsettledAttemptCount'] == 1
    assert cost['unsettledTotal'] == .25


def test_v3t34_invoice_survives_failed_report_publication(tmp_path, monkeypatch):
    from backend.app.provider_billing import ProviderResult, ProviderUsage
    from backend.app.report_store import ReportStore
    def adapter(*a, **kw):
        return ProviderResult(_interprets(*a, **kw), ProviderUsage('invoice-known', '.12', True))
    storage, mid, gateway = gateway_fixture(tmp_path, adapter)
    monkeypatch.setattr(ReportStore, 'publish', lambda *a, **k: (_ for _ in ()).throw(OSError('disk failure')))
    with pytest.raises(OSError): run(gateway, mid)
    assert storage.job_ledger.cost_summary()['actualTotal'] == .12


def test_v3t31_truthful_overrun_blocks_new_paid_requests(tmp_path):
    from backend.app.provider_billing import ProviderResult, ProviderUsage
    calls = []
    def adapter(*a, **kw):
        calls.append(1)
        return ProviderResult(_interprets(*a, **kw), ProviderUsage('invoice-high', '.40', True))
    storage, mid, gateway = gateway_fixture(tmp_path, adapter)
    assert run(gateway, mid)['costSummary']['actualTotal'] == .40
    assert 'BUDGET_BREACH' in storage.job_ledger.cost_summary()['reasonCodes']
    with pytest.raises(ProviderDenied, match='BUDGET_EXHAUSTED'):
        run(gateway, mid, key='new')
    assert calls == [1]


def test_v3t34_before_dispatch_proof_releases_reservation(tmp_path):
    from backend.app.provider_billing import ProviderNotDispatched
    def adapter(*a, **kw): raise ProviderNotDispatched('validation before transport')
    storage, mid, gateway = gateway_fixture(tmp_path, adapter)
    with pytest.raises(ProviderNotDispatched): run(gateway, mid)
    assert storage.job_ledger.cost_summary()['actualTotal'] == 0.0


def test_v3t33_unsupported_components_and_input_size_refused():
    with pytest.raises(ValueError): fake_policy(billable_components=('input_bytes', 'tools'))
    policy = fake_policy(max_input_bytes=2)
    with pytest.raises(ValueError, match='INPUT_BOUND_EXCEEDED'):
        policy.bind(prompt='three', task='report', model='test-model')


def test_v3t32_keyless_replay_of_same_evidence_does_not_buy_a_second_report(tmp_path):
    calls = []
    def adapter(*a, **kw):
        calls.append(1)
        return _interprets(*a, **kw)
    storage, mid, gateway = gateway_fixture(tmp_path, adapter)
    first = gateway.execute(mid, 'tactical_report', requested_provider='cloud')
    second = gateway.execute(mid, 'tactical_report', requested_provider='cloud')
    assert first['reportId'] == second['reportId'] and calls == [1]
    assert storage.job_ledger.cost_for(first['requestId'])['attemptCount'] == 1
    assert storage.job_ledger.cost_summary()['attemptCount'] == 2  # Includes fixture's local processing job.


def test_v3t32_explicit_reconciled_retry_keeps_one_logical_budget(tmp_path):
    from backend.app.provider_billing import ProviderResult, ProviderUsage
    from backend.app.workbench.errors import ReconciliationRequired
    calls=[]
    def adapter(*a,**kw):
        calls.append(kw['request_id'])
        if len(calls)==1:raise TimeoutError('dispatched')
        return ProviderResult(_interprets(*a,**kw),ProviderUsage('second-invoice','.10',True))
    storage,mid,gateway=gateway_fixture(tmp_path,adapter)
    gateway.settings=replace(gateway.settings,provider_call_reservation=.5)
    with pytest.raises(TimeoutError):run(gateway,mid)
    with pytest.raises(ReconciliationRequired):run(gateway,mid)
    req=[r for r in storage.job_ledger.requests.values() if r.scope=='provider'][0]
    attempt=storage.job_ledger.latest_attempt(req.requestId)
    storage.job_ledger.reconcile_attempt(attempt.attemptId,provider_outcome='failed',settled_cost=.1,receipt_id='first-invoice')
    response=gateway.execute(mid,'tactical_report',requested_provider='cloud',
        body={'requireProvider':True,'requestId':'logical-report','retry':True,'retryOfAttemptId':attempt.attemptId})
    assert response['costSummary']['authorisedBudget']==.5
    assert response['costSummary']['attemptCount']==2
    assert response['costSummary']['actualTotal']==.2
    assert len(calls)==2 and calls[0]==calls[1]
