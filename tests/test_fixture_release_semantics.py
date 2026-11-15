"""Authenticated fixture-only release and explicit authored review input."""
from copy import deepcopy
from pathlib import Path
import json
from unittest.mock import patch
import pytest
from test_phase2_jobs import setup
from sourceroi.live.fixture_execution import authorize
from sourceroi.live.semantic_store import SemanticStore


def prepared(s,*,mode='valid',max_attempts=8):
    cfg,store,jobs,actor,spec,approval=s
    permit=authorize(jobs,actor,spec,max_attempts=max_attempts,max_seconds=60)
    values={'baseline':{'returns':'30','warranty':'365'},'candidate':{'returns':'14','warranty':'365'}}
    j=jobs.submit(actor,'fixture-release-request-01',spec,approval,operation='fixture_release',fixture_authorization=permit['id'],fixture_responses=values,fixture_mode=mode)
    return j,permit


def test_real_release_code_uses_bounded_fixture_transport_only(setup):
    _,store,jobs,*_=setup;j,permit=prepared(setup)
    with patch('sourceroi.live.provider._post',side_effect=AssertionError('No network')):
        result=jobs.run_one('fixture-worker-release-1')
    assert result['state']=='COMPLETED',result
    assert result['result']['kind']=='fixture_release'
    assert result['result']['verdict'] in ('REVIEW','BLOCK')
    assert result['result']['provider_attempts']==3
    with store.connect() as c:rows=[dict(r) for r in c.execute('SELECT * FROM job_attempts')]
    assert all(r['state']=='COMPLETED' for r in rows)
    assert len({r['id'] for r in rows})==3 and all(json.loads(r['usage'])['prompt_tokens']==3 for r in rows)
    assert all(json.loads(r['request'])['attempt_id']==r['id'] for r in rows)


@pytest.mark.parametrize('mode',['missing_usage','timeout','partial','child_call','failure'])
def test_incomplete_fixture_cannot_accept_or_retry(setup,mode):
    _,store,jobs,*_=setup;j,_=prepared(setup,mode=mode)
    result=jobs.run_one('fixture-worker-release-1')
    assert result['state']=='INCONCLUSIVE'
    with store.connect() as c:rows=[dict(r) for r in c.execute('SELECT * FROM job_attempts')]
    assert len(rows)==1 and rows[0]['state']=='UNKNOWN' and rows[0]['usage'] is None
    assert jobs.run_one('fixture-worker-release-2') is None


def test_attempt_cap_is_provider_attempts_not_logical_tasks(setup):
    _,store,jobs,*_=setup;j,_=prepared(setup,max_attempts=1)
    result=jobs.run_one('fixture-worker-release-1')
    assert result['state']=='INCONCLUSIVE'
    with store.connect() as c:assert c.execute('SELECT COUNT(*) FROM job_attempts').fetchone()[0]==1


def test_revoked_fixture_authorization_rejects_before_attempt(setup):
    _,store,jobs,*_=setup;j,p=prepared(setup)
    with store.connect() as c:c.execute('UPDATE fixture_authorizations SET revoked=1 WHERE id=?',(p['id'],))
    assert jobs.run_one('fixture-worker-release-1')['state']=='INCONCLUSIVE'
    with store.connect() as c:assert c.execute('SELECT COUNT(*) FROM job_attempts').fetchone()[0]==0


def reviewer(store):return store.login('reviewer','Authored fixture password 2026')['user']


def decision(packet):
    sample=packet['sample'];quote=sample['context'][0]['text'];cid=sample['context'][0]['id']
    return {'binding':packet['binding'],'decision':'supported','claims':[{'start':0,'end':len(sample['answer']),'verdict':'supported','evidence':[{'id':cid,'quote':quote}]}],
        'dimensions':{'semantic_correctness':True,'citation_correctness':True,'scope_appropriate':True,'uses_outdated_fact':False},
        'rationale':'Authored fixture claim assertion, not a human review','authorization_basis':'Development test role, no externally verified independence'}


def test_authenticated_semantic_record_is_immutable_and_never_independent(setup):
    _,store,jobs,*_=setup;j,_=prepared(setup);jobs.run_one('fixture-worker-release-1')
    reviews=SemanticStore(jobs);packet=reviews.packet(j['id'],'warranty');r=reviewer(store)
    row=reviews.put(j['id'],'warranty',r,**decision(packet))
    assert row['reviewer']['id']==r['id'] and not row['independence_verified_externally']
    assert reviews.assess(j['id'])['verdict']!='ACCEPT'
    with pytest.raises(ValueError,match='already recorded'):reviews.put(j['id'],'warranty',r,**decision(packet))


def test_stale_or_substituted_semantic_record_rejected(setup):
    cfg,store,jobs,*_=setup;j,_=prepared(setup);jobs.run_one('fixture-worker-release-1')
    reviews=SemanticStore(jobs);p=reviews.packet(j['id'],'warranty');r=reviewer(store)
    bad=decision(p);bad['binding']='forged'
    with pytest.raises(ValueError,match='binding'):reviews.put(j['id'],'warranty',r,**bad)
    (Path(cfg['_root'])/'sources/policy/returns.json').write_text('{"return_days":99}')
    with pytest.raises(ValueError,match='Stale'):reviews.put(j['id'],'warranty',r,**decision(p))


def test_revoked_semantic_reviewer_invalidates_existing_record(setup):
    _,store,jobs,*_=setup;j,_=prepared(setup);jobs.run_one('fixture-worker-release-1')
    reviews=SemanticStore(jobs);p=reviews.packet(j['id'],'warranty');reviews.put(j['id'],'warranty',reviewer(store),**decision(p))
    store.set_role('reviewer','reviewer')
    assert reviews.assess(j['id'])['stale_judgments']==1


def test_negative_semantic_judgment_blocks(setup):
    _,store,jobs,*_=setup;j,_=prepared(setup);jobs.run_one('fixture-worker-release-1')
    reviews=SemanticStore(jobs);p=reviews.packet(j['id'],'warranty');d=decision(p);d['decision']='contradicted';d['claims'][0]['verdict']='contradicted';d['dimensions']['semantic_correctness']=False
    reviews.put(j['id'],'warranty',reviewer(store),**d)
    assert reviews.assess(j['id'])['verdict']=='BLOCK'


def test_authenticated_api_binding_review_roles_and_extra_fields(setup):
    from fastapi.testclient import TestClient
    from sourceroi.live.api import create_app
    cfg,store,jobs,actor,spec,approval=setup;app=create_app(cfg['_root'])
    with TestClient(app,base_url='http://localhost') as client:
        login=client.post('/api/v2/auth/login',json={'username':'operator','password':'Authored fixture password 2026'}).json()
        h={'origin':'http://localhost','x-csrf-token':login['csrf'],'idempotency-key':'api-fixture-release-01'}
        permission=client.post('/api/v2/fixture-authorizations',json={'specification':spec,'max_attempts':8,'scope':'benchmark'},headers=h)
        assert permission.status_code==201 and permission.json()['real_generation_authorized'] is False
        values={'baseline':{'returns':'30','warranty':'365'},'candidate':{'returns':'14','warranty':'365'}}
        payload={'operation':'fixture_release','specification':spec,'approval':approval,'fixture_authorization':permission.json()['id'],'fixture_responses':values}
        response=client.post('/api/v2/jobs',json=payload,headers=h);assert response.status_code==202,response.text
        jid=response.json()['job']['id'];jobs.run_one('fixture-worker-api-1')
        assert client.get('/api/v2/jobs/'+jid).json()['job']['result']['fixture_only']
        assert client.get('/api/v2/jobs/'+jid+'/review-packet?task_id=warranty').status_code==404
        assert client.post('/api/v2/knowledge/release',json={},headers=h).status_code==403
    with TestClient(app,base_url='http://localhost') as client:
        login=client.post('/api/v2/auth/login',json={'username':'reviewer','password':'Authored fixture password 2026'}).json()
        h={'origin':'http://localhost','x-csrf-token':login['csrf']}
        packet=client.get('/api/v2/jobs/'+jid+'/review-packet?task_id=warranty').json()
        bad={**decision(packet),'task_id':'warranty','reviewer':'admin','independence_verified_externally':True}
        assert client.post('/api/v2/jobs/'+jid+'/semantic-reviews',json=bad,headers=h).status_code==422
        result=client.post('/api/v2/jobs/'+jid+'/semantic-reviews',json={**decision(packet),'task_id':'warranty'},headers=h)
        assert result.status_code==201 and result.json()['reviewer']['name']=='reviewer'
        assert not result.json()['independence_verified_externally']
        assert client.get('/api/v2/jobs/'+jid+'/assessment').json()['verdict']!='ACCEPT'


def test_actual_worker_kill_after_fixture_dispatch_leaves_unknown(setup):
    import subprocess,sys,time
    cfg,store,jobs,*_=setup;j,_=prepared(setup,mode='timeout')
    code='from sourceroi.live.security import SecurityStore;from sourceroi.live.durable_jobs import Jobs;import sys;Jobs(SecurityStore(sys.argv[1])).run_one("killed-fixture-worker")'
    process=subprocess.Popen([sys.executable,'-c',code,cfg['_root']],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        deadline=time.monotonic()+5;state=None
        while time.monotonic()<deadline and process.poll() is None:
            with store.connect() as c:row=c.execute('SELECT state FROM job_attempts WHERE job=?',(j['id'],)).fetchone()
            state=row[0] if row else None
            if state=='DISPATCHED':break
            time.sleep(.02)
        assert state=='DISPATCHED';process.kill();process.wait(timeout=3)
        now=store.clock();store.clock=lambda:now+16;jobs.recover()
        assert jobs.get(j['id'])['state']=='INCONCLUSIVE'
        with store.connect() as c:assert c.execute('SELECT state FROM job_attempts WHERE job=?',(j['id'],)).fetchone()[0]=='UNKNOWN'
        assert jobs.run_one('replacement-fixture-worker') is None
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=3)


def test_recovery_after_parser_failure_and_fixture_job_preserves_history(setup,tmp_path):
    from sourceroi.live.ingest import _extract
    from sourceroi.live.workspace_recovery import backup,restore
    from sourceroi.live.security import SecurityStore
    from sourceroi.live.durable_jobs import Jobs
    cfg,store,jobs,*_=setup
    bad=tmp_path/'malformed.pdf';bad.write_bytes(b'%PDF-invalid')
    with pytest.raises(ValueError):_extract(bad)
    j,_=prepared(setup,mode='missing_usage');jobs.run_one('fixture-worker-recovery')
    archive=backup(cfg['_root'],tmp_path/'recovery.zip',quiesced=True)
    recovered=restore(archive['archive'],tmp_path/'restored',expected_sha256=archive['sha256'])
    newstore=SecurityStore(recovered['workspace']);newjobs=Jobs(newstore)
    assert newjobs.run_one('restored-fixture-worker') is None
    with newstore.connect() as c:
        assert c.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]==0
        assert c.execute('SELECT COUNT(*) FROM approvals').fetchone()[0]==0
    histories=list((Path(recovered['workspace'])/'.sourceroi/restored-history').glob('security-provenance-*.json'))
    history=json.loads(histories[0].read_text());assert history['job_attempts'][0]['state']=='UNKNOWN'


def test_tampered_fixture_terminal_cannot_pass_reconciliation(setup):
    from sourceroi.live.fixture_execution import reconcile
    _,store,jobs,*_=setup;j,_=prepared(setup);result=jobs.run_one('fixture-worker-seal-1')
    assert reconcile(jobs,result)==result['result']['reconciliation']
    with store.connect() as c:
        row=c.execute('SELECT id,response FROM job_attempts LIMIT 1').fetchone();body=json.loads(row['response']);body['attempt_id']='forged'
        c.execute('UPDATE job_attempts SET response=? WHERE id=?',(json.dumps(body),row['id']))
    with pytest.raises(ValueError,match='reconciliation mismatch'):reconcile(jobs,result)
    assert SemanticStore(jobs).assess(j['id'])['verdict']=='INCONCLUSIVE'
