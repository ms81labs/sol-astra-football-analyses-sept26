"""Real local processes and API/WebSocket reads. No model or worker dispatch."""
import multiprocessing as mp
import time
from decimal import Decimal
import pytest
from backend.app.workbench.jobs import DurableJobLedger, JobRequest

pytestmark = pytest.mark.integration


def _reserve(path, pipe):
    from backend.app.provider_gateway import ProviderBudgetLedger
    ledger = ProviderBudgetLedger(path, .3)
    pipe.send('ready'); pipe.recv()
    pipe.send([ledger.reserve(match_id='match', task_type='report', amount=.1) for _ in range(3)])
    pipe.close()


def _claim(path, pipe):
    ledger = DurableJobLedger(path)
    pipe.send('ready'); pipe.recv()
    pipe.send(ledger.claim_dispatch('request', owner_id='worker'))
    pipe.close()


def _claimed_then_pause(path, pipe):
    ledger = DurableJobLedger(path)
    assert ledger.claim_dispatch('request', owner_id='worker', phase='running')
    pipe.send('dispatched'); pipe.recv()


def _request():
    return JobRequest(requestId='request',matchId='match',sourceSha256='a'*64,
        intervalStart=0,intervalEnd=1,temporalPolicy='source_global_grid',decoderVersion='fixture',
        modelHash='fixture',outputSchema='fixture',budget=1,authorisedLocation='daytona')


def _two_processes(target, path):
    context=mp.get_context('spawn'); channels=[]; processes=[]
    try:
        for _ in range(2):
            parent,child=context.Pipe()
            process=context.Process(target=target,args=(path,child));process.start();child.close()
            processes.append(process);channels.append(parent)
        for channel in channels:
            assert channel.poll(30), 'child failed to initialise'
            assert channel.recv()=='ready'
        for channel in channels:channel.send('go')
        results=[]
        for channel in channels:
            assert channel.poll(30), 'child failed to return'
            results.append(channel.recv())
        for process in processes:
            process.join(10); assert process.exitcode==0
        return results
    finally:
        for process in processes:
            if process.is_alive():process.kill();process.join(5)
        for channel in channels:channel.close()


def test_v3t31_two_process_budget_admission_is_exact_and_serialised(tmp_path):
    path=tmp_path/'shared.db'; DurableJobLedger(path)
    results=_two_processes(_reserve,path)
    amounts=[Decimal(str(v)) for group in results for v in group if v is not None]
    assert amounts==[Decimal('.1')]*3
    ledger=DurableJobLedger(path)
    assert ledger.cost_summary()['attemptCount']==3
    assert ledger.cost_summary()['outstandingReserved']==.3
    assert ledger.cost_summary()['actualTotal'] is None


def test_v3t32_two_processes_claim_one_job_dispatch(tmp_path):
    path=tmp_path/'shared.db'; ledger=DurableJobLedger(path)
    ledger.admit(_request(), mode='submit',owner_id='worker',lease_seconds=60)
    assert sorted(_two_processes(_claim,path))==[False,True]
    assert ledger.cost_summary()['attemptCount']==1


def test_v3t34_killed_dispatch_keeps_liability_after_reopen(tmp_path):
    from backend.app.workbench.errors import ReconciliationRequired
    path=tmp_path/'shared.db';ledger=DurableJobLedger(path)
    attempt=ledger.admit(_request(),mode='submit',owner_id='worker',lease_seconds=60)
    context=mp.get_context('spawn'); parent,child=context.Pipe()
    process=context.Process(target=_claimed_then_pause,args=(path,child));process.start();child.close()
    try:
        assert parent.poll(30) and parent.recv()=='dispatched'
        process.kill();process.join(10);assert process.exitcode != 0
        reopened=DurableJobLedger(path)
        reopened.reclaim_expired(now=time.time()+120)
        cost=reopened.cost_for('request')
        assert cost['actualTotal'] is None and cost['unsettledTotal']==1
        with pytest.raises(ReconciliationRequired): reopened.submit(_request())
        reopened.reconcile_attempt(attempt.attemptId,provider_outcome='not_found',settled_cost=0,
            receipt_id='confirmed-no-charge',no_charge_reason='PROVIDER_CONFIRMED_NO_CHARGE')
        assert reopened.cost_for('request')['actualTotal']==0
        assert reopened.retry('request').sequence==2
    finally:
        if process.is_alive():process.kill();process.join(5)
        parent.close()


def test_v3t29_actual_http_socket_and_receipt_share_costs(tmp_path):
    from backend.tests.test_audit_v3_c03_reports import FIXTURE
    from backend.app.storage import Storage
    from backend.app.schemas import MatchConfig
    from backend.app.main import create_app
    from fastapi.testclient import TestClient
    storage=Storage(tmp_path/'store')
    mid=storage.create_match('Billing fixture','tracking_json',FIXTURE.name,FIXTURE,MatchConfig()).id
    job,_=storage.ensure_job(mid,'billing-job',budget=1,authorised_location='daytona')
    with TestClient(create_app(storage_root=storage.storage_root,run_jobs_inline=False),base_url='http://127.0.0.1') as client:
        ledger=storage.job_ledger
        for phase in ('submitted','running','outcome_unknown','reconciled'):
            current=ledger.latest_attempt(job.id)
            if phase=='reconciled':
                ledger.reconcile_attempt(current.attemptId,provider_outcome='complete',settled_cost=.2,receipt_id='final')
            elif phase!='submitted':
                ledger.transition(current.attemptId,expected_revision=current.revision,owner_id=current.ownerId,status=phase)
            receipt=ledger.receipt(job.id).costSummary.model_dump(mode='json')
            http=client.get(f'/api/jobs/{job.id}').json()
            route=client.get(f'/api/jobs/{job.id}/cost').json()
            match=client.get(f'/api/matches/{mid}/cost').json()['byCurrency']['USD']
            with client.websocket_connect(f'ws://127.0.0.1:8000/ws/jobs/{job.id}', headers={'Origin':'http://localhost:5173'}) as socket:
                message=socket.receive_json()
            assert http['costSummary']==message['costSummary']==receipt
            assert {k:route[k] for k in receipt}==receipt
            assert {k:match[k] for k in receipt}==receipt
            assert receipt['actualTotal']==(.2 if phase=='reconciled' else None)


def test_v3t29_compatibility_budget_and_charges_do_not_invent_incurring(tmp_path):
    from backend.tests.test_audit_v3_c03_reports import FIXTURE
    from backend.app.main import create_app
    from backend.app.schemas import MatchConfig
    from fastapi.testclient import TestClient
    app=create_app(storage_root=tmp_path/'store',run_jobs_inline=False)
    storage=app.state.storage
    mid=storage.create_match('Billing','tracking_json',FIXTURE.name,FIXTURE,MatchConfig()).id
    job,_=storage.ensure_job(mid,'billing',budget=1,authorised_location='daytona')
    with TestClient(app,base_url='http://127.0.0.1') as client:
        charges=client.get(f'/api/jobs/{job.id}/charges').json()
        budget=client.get(f'/api/jobs/{job.id}/budget').json()
        assert charges['incurred']==0, 'a reservation is not an incurred charge'
        assert charges['actualTotal'] is None
        assert charges['outstandingReserved']==1
        assert budget['reconcile']['actual'] is None
        assert budget['reconcile']['variance'] is None
        current=storage.job_ledger.latest_attempt(job.id)
        storage.job_ledger.reconcile_attempt(current.attemptId,provider_outcome='complete',settled_cost=0,receipt_id='invoice-zero')
        assert client.get(f'/api/jobs/{job.id}/charges').json()['actualTotal']==0
        assert client.get(f'/api/jobs/{job.id}/budget').json()['reconcile']['actual']==0


@pytest.mark.parametrize('value',[True,False,'NaN',None,'100000000000.000000000001'])
def test_v3t31_job_admission_rejects_invalid_money_before_creating_job(tmp_path,value):
    from backend.tests.test_audit_v3_c03_reports import FIXTURE
    from backend.app.main import create_app
    from backend.app.schemas import MatchConfig
    from fastapi.testclient import TestClient
    app=create_app(storage_root=tmp_path/'store',run_jobs_inline=False)
    storage=app.state.storage
    mid=storage.create_match('Billing','tracking_json',FIXTURE.name,FIXTURE,MatchConfig()).id
    with TestClient(app,base_url='http://127.0.0.1') as client:
        response=client.post(f'/api/matches/{mid}/jobs',json={'requestId':'invalid-cost','budget':value})
        assert response.status_code==422
    assert not storage.job_ledger.has_request('invalid-cost')


def test_v3t32_paid_http_retry_requires_anchor_and_does_not_reset_completed_replay(tmp_path,monkeypatch):
    from backend.tests.test_audit_v3_c03_reports import FIXTURE
    from backend.app.main import create_app
    from backend.app.schemas import MatchConfig
    from fastapi.testclient import TestClient
    app=create_app(storage_root=tmp_path/'store',run_jobs_inline=False)
    storage=app.state.storage;ledger=storage.job_ledger
    mid=storage.create_match('Billing','tracking_json',FIXTURE.name,FIXTURE,MatchConfig()).id
    job,_=storage.ensure_job(mid,'paid',budget=1,authorised_location='daytona')
    first=ledger.latest_attempt(job.id)
    ledger.transition(first.attemptId,expected_revision=first.revision,owner_id=first.ownerId,status='failed',actualCost=.1)
    calls=[];monkeypatch.setattr(app.state.runner,'_dispatch',calls.append)
    with TestClient(app,base_url='http://127.0.0.1') as client:
        missing=client.post(f'/api/jobs/{job.id}/retry')
        assert missing.status_code==409
        body={'retryOfAttemptId':first.attemptId}
        response=client.post(f'/api/jobs/{job.id}/retry',json=body)
        assert response.status_code==200,response.text
        second=ledger.latest_attempt(job.id)
        ledger.transition(second.attemptId,expected_revision=second.revision,owner_id=second.ownerId,status='complete',actualCost=.1)
        storage.update_job(job.id,status='completed',progress=1,message='Complete')
        replay=client.post(f'/api/jobs/{job.id}/retry',json=body)
        assert replay.status_code==200,replay.text
        assert replay.json()['status']=='completed'
        assert ledger.receipt(job.id).attemptCount==2 and calls==[job.id]
