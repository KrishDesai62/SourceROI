"""Offline durable orchestration; temporary authored identities, never inference."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from examples.knowledge_change.demo import workspace
from sourceroi.live.config import read_config
from sourceroi.live.data_ci import freeze
from sourceroi.live import assurance as a
from sourceroi.live.security import SecurityStore
from sourceroi.live.durable_jobs import Jobs,JobConflict

@pytest.fixture
def setup(tmp_path):
    cfg=workspace(tmp_path/'project');store=SecurityStore(cfg['_root'],initialize=True)
    for role in ('operator','reviewer'):store.add_user(role,'Authored fixture password 2026',role)
    actor=store.login('operator','Authored fixture password 2026')['user'];reviewer=store.login('reviewer','Authored fixture password 2026')['user']
    sid='a'*32;snapshot=Path(cfg['_root'])/'.sourceroi/snapshots'/sid;freeze(cfg,snapshot)
    (Path(cfg['_root'])/'sources/policy/returns.json').write_text('{"return_days":14}')
    cfg=read_config(cfg['_root']);spec=a.propose(read_config(snapshot),cfg)
    store.register_plan(spec,sid)
    review=a.review(spec,reviewer='reviewer',rationale='Authored development fixture only',expected_changes={'returns':'14'},protected_tasks=['warranty'],expected_evidence={'returns':[{'document_id':'policy::returns.json','quote':'14'}]})
    approval=store.bind_approval(review,reviewer)
    return cfg,store,Jobs(store),actor,spec,approval


def submit(s,key='request-key-0001',**kwargs):
    _,_,jobs,actor,spec,approval=s
    return jobs.submit(actor,key,spec,approval,**kwargs)


def test_submission_retries_restart_and_parallel_duplicates(setup):
    cfg,store,jobs,actor,spec,approval=setup
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(lambda _:submit(setup),range(8)))
    assert len({r['id'] for r in results})==1
    assert Jobs(SecurityStore(cfg['_root'])).submit(actor,'request-key-0001',spec,approval)['id']==results[0]['id']
    with pytest.raises(JobConflict):submit(setup,max_seconds=30)
    with pytest.raises(ValueError,match='consumed'):submit(setup,key='different-key-0002')
    with store.connect() as c:
        assert c.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]==1
        assert c.execute('SELECT used FROM approvals').fetchone()[0]==1


def test_atomic_approval_and_job_rollback_on_database_failure(setup):
    _,store,jobs,*_=setup
    with store.connect() as c:c.execute("CREATE TRIGGER fixture_failure BEFORE UPDATE ON approvals BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
    with pytest.raises(Exception,match='fixture failure'):submit(setup)
    with store.connect() as c:
        assert c.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]==0
        assert c.execute('SELECT COUNT(*) FROM job_events').fetchone()[0]==0
        assert c.execute('SELECT used FROM approvals').fetchone()[0]==0


def test_offline_worker_cannot_dispatch_or_accept(setup):
    _,_,jobs,*_=setup;j=submit(setup)
    with patch('sourceroi.live.engine.run_chat',side_effect=AssertionError('No generation')):
        result=jobs.run_one('fixture-worker-1')
    assert result['id']==j['id'] and result['state']=='COMPLETED'
    assert result['result']['verdict']=='INCONCLUSIVE' and result['result']['generation_attempts']==0
    assert [e['state'] for e in jobs.events(j['id'])]==['CREATED','QUEUED','CLAIMED','RUNNING','COMPLETED']
    assert jobs.run_one('fixture-worker-2') is None
    assert [e['fence'] for e in jobs.events(j['id'])][-3:]==[1,1,1]


def test_leases_fence_and_recovery_never_redispatch(setup):
    _,store,jobs,*_=setup;j=submit(setup);claimed=jobs.claim('fixture-worker-1',lease_seconds=1)
    assert not jobs.claim('fixture-worker-2')
    jobs.reserve(j['id'],'fixture-worker-1',claimed['fence']);jobs.checkpoint(j['id'],'fixture-worker-1',claimed['fence'],{'answer':'partial fixture'})
    now=store.clock();store.clock=lambda:now+2
    assert jobs.recover()==[j['id']]
    assert jobs.get(j['id'])['state']=='INCONCLUSIVE' and jobs.get(j['id'])['partial']
    with pytest.raises(ValueError,match='ownership'):jobs.finish(j['id'],'fixture-worker-1',claimed['fence'])
    assert not jobs.claim('fixture-worker-2')


def test_cancellation_before_and_after_reservation(setup):
    _,_,jobs,actor,*_=setup;j=submit(setup)
    assert jobs.cancel(j['id'],actor)['state']=='CANCELLED'
    assert jobs.claim('fixture-worker-1') is None


def test_cancellation_inflight_is_acknowledged_as_uncertain(setup):
    _,_,jobs,actor,*_=setup;j=submit(setup);claimed=jobs.claim('fixture-worker-1')
    jobs.reserve(j['id'],'fixture-worker-1',claimed['fence'])
    assert jobs.cancel(j['id'],actor)['state']=='CANCEL_REQUESTED'
    jobs.finish(j['id'],'fixture-worker-1',claimed['fence'])
    assert jobs.get(j['id'])['state']=='INCONCLUSIVE' and jobs.get(j['id'])['result']['usage'] is None


def test_cancellation_before_reservation_prevents_start(setup):
    _,_,jobs,actor,*_=setup;j=submit(setup);claimed=jobs.claim('fixture-worker-1');jobs.cancel(j['id'],actor)
    with pytest.raises(ValueError,match='restart'):jobs.reserve(j['id'],'fixture-worker-1',claimed['fence'])
    jobs.finish(j['id'],'fixture-worker-1',claimed['fence'],state='CANCELLED')
    assert jobs.get(j['id'])['state']=='CANCELLED'


def test_revocation_after_submission_blocks_execution(setup):
    _,store,jobs,*_=setup;j=submit(setup);store.revoke_user('reviewer')
    result=jobs.run_one('fixture-worker-1')
    assert result['state']=='INCONCLUSIVE' and result['reservation'] is None


def test_deadlines_before_claim_and_during_execution(setup):
    _,store,jobs,*_=setup;j=submit(setup,max_seconds=1);now=store.clock();store.clock=lambda:now+2
    jobs.recover();assert jobs.get(j['id'])['state']=='CANCELLED'


def test_generation_and_stale_inputs_fail_closed(setup):
    cfg,_,_,_,_,_=setup
    with pytest.raises(ValueError,match='Generation jobs disabled'):submit(setup,operation='generate')
    (Path(cfg['_root'])/'sources/policy/returns.json').write_text('{"return_days":99}')
    with pytest.raises(ValueError,match='Stale'):submit(setup)


def test_authenticated_http_retry_restart_and_read_isolation(setup):
    from sourceroi.live.api import create_app
    cfg,_,jobs,actor,spec,approval=setup
    with TestClient(create_app(cfg['_root']),base_url='http://localhost') as client:
        login=client.post('/api/v2/auth/login',json={'username':'operator','password':'Authored fixture password 2026'}).json()
        headers={'origin':'http://localhost','x-csrf-token':login['csrf'],'idempotency-key':'http-request-0001'}
        body={'specification':spec,'approval':approval}
        response=client.post('/api/v2/jobs',json=body,headers=headers)
        assert response.status_code==202,response.text
        jid=response.json()['job']['id']
        assert client.post('/api/v2/jobs',json=body,headers=headers).json()['job']['id']==jid
        assert client.get('/api/v2/jobs/'+jid).status_code==200
        assert client.post('/api/v2/knowledge/release',json={},headers=headers).status_code==403
    with TestClient(create_app(cfg['_root']),base_url='http://localhost') as client:
        login=client.post('/api/v2/auth/login',json={'username':'reviewer','password':'Authored fixture password 2026'}).json()
        assert client.get('/api/v2/jobs/'+jid).status_code==404


@pytest.mark.parametrize('phase',['claimed','reserved','partial','response'])
def test_actual_killed_worker_has_no_automatic_retry(setup,phase):
    cfg,store,jobs,*_=setup;j=submit(setup)
    code='''import sys,time
from sourceroi.live.security import SecurityStore
from sourceroi.live.durable_jobs import Jobs
j=Jobs(SecurityStore(sys.argv[1]));r=j.claim('process-worker-1',lease_seconds=1)
if sys.argv[2]!='claimed':j.reserve(r['id'],r['worker'],r['fence'])
if sys.argv[2]=='partial':j.checkpoint(r['id'],r['worker'],r['fence'],{'fixture_partial':True})
if sys.argv[2]=='response':result={'fixture_response':'received_but_not_committed'}
print('ready',flush=True);time.sleep(30)
'''
    p=subprocess.Popen([sys.executable,'-c',code,cfg['_root'],phase],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        assert p.stdout.readline().strip()=='ready';p.kill();p.wait(timeout=5)
        now=store.clock();store.clock=lambda:now+2;jobs.recover()
        assert jobs.get(j['id'])['state']==('CANCELLED' if phase=='claimed' else 'INCONCLUSIVE')
        assert jobs.claim('new-process-worker') is None
    finally:
        if p.poll() is None:p.kill();p.wait(timeout=5)


def test_two_real_processes_compete_for_one_job(setup):
    cfg,_,jobs,*_=setup;j=submit(setup)
    code="from sourceroi.live.security import SecurityStore; from sourceroi.live.durable_jobs import Jobs; import sys,json; j=Jobs(SecurityStore(sys.argv[1])).claim(sys.argv[2]); print(json.dumps(j['id'] if j else None))"
    processes=[subprocess.Popen([sys.executable,'-c',code,cfg['_root'],'process-worker-'+str(i)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for i in range(2)]
    results=[]
    for p in processes:
        out,err=p.communicate(timeout=15);assert p.returncode==0,err;results.append(json.loads(out))
    assert results.count(j['id'])==1 and results.count(None)==1


def test_heartbeat_and_foreign_fence_rejection(setup):
    _,store,jobs,*_=setup;j=submit(setup);r=jobs.claim('fixture-worker-1',lease_seconds=1)
    before=r['lease'];jobs.heartbeat(j['id'],r['worker'],r['fence'],lease_seconds=30)
    assert jobs.get(j['id'])['lease']>before
    with pytest.raises(ValueError,match='ownership'):jobs.checkpoint(j['id'],'foreign-worker-1',r['fence'],{})
    with pytest.raises(ValueError,match='ownership'):jobs.finish(j['id'],r['worker'],r['fence']-1)


def test_uncertain_finish_cannot_accept_and_partial_is_preserved(setup):
    _,_,jobs,*_=setup;j=submit(setup);r=jobs.claim('fixture-worker-1');jobs.reserve(j['id'],r['worker'],r['fence'])
    jobs.checkpoint(j['id'],r['worker'],r['fence'],{'received':'partial response','usage':None})
    with pytest.raises(ValueError,match='ACCEPT'):jobs.finish(j['id'],r['worker'],r['fence'],result={'verdict':'ACCEPT'})
    jobs.finish(j['id'],r['worker'],r['fence'],state='INCONCLUSIVE',result={'verdict':'INCONCLUSIVE','usage':None})
    assert jobs.get(j['id'])['partial']['usage'] is None
    with pytest.raises(ValueError):jobs.reserve(j['id'],r['worker'],r['fence'])


def test_revocation_between_reservation_and_commit(setup):
    _,store,jobs,*_=setup;j=submit(setup);r=jobs.claim('fixture-worker-1');jobs.reserve(j['id'],r['worker'],r['fence'])
    store.set_role('reviewer','viewer')
    jobs.finish(j['id'],r['worker'],r['fence'],result={'verdict':'INCONCLUSIVE'})
    assert jobs.get(j['id'])['state']=='INCONCLUSIVE'


def test_real_submission_transaction_kill_rolls_back_receipt_and_job(setup):
    cfg,store,jobs,actor,spec,approval=setup
    fixture=Path(cfg['_root'])/'fixture-submit.json';fixture.write_text(json.dumps({'actor':actor,'spec':spec,'approval':approval}))
    code='''import json,sys,time
from sourceroi.live.security import SecurityStore
from sourceroi.live.durable_jobs import Jobs
s=SecurityStore(sys.argv[1]);j=Jobs(s);d=json.load(open(sys.argv[2]));original=j._move
def stop(*args,**kwargs):
 original(*args,**kwargs);print('uncommitted',flush=True);time.sleep(30)
j._move=stop;j.submit(d['actor'],'killed-request-001',d['spec'],d['approval'])
'''
    p=subprocess.Popen([sys.executable,'-c',code,cfg['_root'],str(fixture)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        assert p.stdout.readline().strip()=='uncommitted';p.kill();p.wait(timeout=5)
        with store.connect() as c:
            assert c.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]==0
            assert c.execute('SELECT used FROM approvals').fetchone()[0]==0
        assert submit(setup)['state']=='QUEUED'
    finally:
        if p.poll() is None:p.kill();p.wait(timeout=5)


def test_expired_receipt_never_creates_job(setup):
    _,store,jobs,*_=setup;now=store.clock();store.clock=lambda:now+3601
    with pytest.raises(ValueError,match='expired'):submit(setup)
    with store.connect() as c:assert c.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]==0


def test_corrupt_payload_cannot_be_replayed_or_executed(setup):
    _,store,jobs,*_=setup;j=submit(setup)
    with store.connect() as c:c.execute("UPDATE jobs SET payload='{}' WHERE id=?",(j['id'],))
    with pytest.raises(ValueError,match='identity mismatch'):jobs.get(j['id'])


def test_cancelled_or_expired_before_reservation_not_restarted(setup):
    _,store,jobs,*_=setup;j=submit(setup);r=jobs.claim('fixture-worker-1',lease_seconds=1);now=store.clock();store.clock=lambda:now+2
    with pytest.raises(ValueError,match='ownership'):jobs.reserve(j['id'],r['worker'],r['fence'])
    jobs.recover();assert jobs.get(j['id'])['state']=='CANCELLED'


def test_restart_in_another_process_returns_existing_submission(setup):
    cfg,_,_,actor,spec,approval=setup;j=submit(setup)
    path=Path(cfg['_root'])/'restart-fixture.json';path.write_text(json.dumps({'actor':actor,'spec':spec,'approval':approval}))
    code="from sourceroi.live.durable_jobs import Jobs; from sourceroi.live.security import SecurityStore; import json,sys; d=json.load(open(sys.argv[2])); print(Jobs(SecurityStore(sys.argv[1])).submit(d['actor'],'request-key-0001',d['spec'],d['approval'])['id'])"
    process=subprocess.run([sys.executable,'-c',code,cfg['_root'],str(path)],capture_output=True,text=True,timeout=15)
    assert process.returncode==0,process.stderr
    assert process.stdout.strip()==j['id']


@pytest.mark.parametrize('change',['password_reset','same_role_change'])
def test_revocation_of_already_consumed_receipt_remains_distinct(setup,change):
    _,store,jobs,*_=setup;j=submit(setup)
    if change=='password_reset':store.reset_password('reviewer','New development fixture password')
    else:store.set_role('reviewer','reviewer')
    result=jobs.run_one('fixture-worker-1')
    assert result['state']=='INCONCLUSIVE' and result['reservation'] is None
    with store.connect() as c:assert c.execute('SELECT COUNT(*) FROM approval_revocations').fetchone()[0]==1


@pytest.mark.parametrize('change',['password_reset','same_role_change'])
def test_submitting_actor_credential_revision_revokes_queued_authority(setup,change):
    _,store,jobs,*_=setup;j=submit(setup)
    if change=='password_reset':store.reset_password('operator','Changed operator fixture password')
    else:store.set_role('operator','operator')
    result=jobs.run_one('fixture-worker-1')
    assert result['state']=='INCONCLUSIVE' and result['reservation'] is None
