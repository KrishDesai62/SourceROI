"""Deterministic identities and reviews; no real operators, model or customer data."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from fastapi.testclient import TestClient
import pytest
from examples.knowledge_change.demo import workspace
from sourceroi.live.api import create_app
from sourceroi.live.security import SecurityStore,COOKIE,hashed
from sourceroi.live import db
from sourceroi.live.assurance import validate_review

PASSWORD='correct horse battery staple fixture'

@pytest.fixture
def secured(tmp_path):
    cfg=workspace(tmp_path/'project')
    store=SecurityStore(cfg['_root'],initialize=True)
    for role in ('viewer','operator','reviewer','admin'):store.add_user(role,PASSWORD,role)
    return cfg,store


def signin(client,name='operator'):
    response=client.post('/api/v2/auth/login',json={'username':name,'password':PASSWORD})
    assert response.status_code==200,response.text
    return {'origin':'http://localhost','x-csrf-token':response.json()['csrf']}


def test_authentication_before_all_data_and_mutations(secured):
    cfg,store=secured
    with TestClient(create_app(cfg['_root']),base_url='http://localhost') as client:
        for path in ('project','runs','ready','knowledge/timeline','runs/not-a-run','auth/session'):
            assert client.get('/api/v2/'+path).status_code==401
        for path in ('runs','knowledge/review','knowledge/plan','knowledge/release','data-ci/freeze','optimize','studies','data-ci'):
            assert client.post('/api/v2/'+path,json={}).status_code==401
        assert client.get('/api/v2/health').json()['authenticated']
        assert client.post('/api/v2/auth/login',json={'username':'operator','password':'incorrect'}).status_code==401
        headers=signin(client)
        assert client.get('/api/v2/project').status_code==200
        assert client.get('/api/v2/auth/session').json()['user']['name']=='operator'
        assert client.post('/api/v2/data-ci/freeze',json={},headers=headers).status_code==200


@pytest.mark.parametrize('role,path',[('viewer','data-ci/freeze'),('operator','knowledge/review'),('reviewer','data-ci/freeze')])
def test_least_privilege_before_handler_validation(secured,role,path):
    cfg,_=secured
    with TestClient(create_app(cfg['_root']),base_url='http://localhost') as client:
        headers=signin(client,role)
        assert client.post('/api/v2/'+path,json={},headers=headers).status_code==403


def test_cookie_flags_csrf_and_session_revocation(secured):
    cfg,store=secured
    with TestClient(create_app(cfg['_root']),base_url='http://localhost') as client:
        headers=signin(client);cookie=client.cookies.get(COOKIE)
        assert store.authenticate(cookie)
        for h in ({},{'origin':'http://localhost'},{'x-csrf-token':headers['x-csrf-token']},{**headers,'x-csrf-token':'forged'}):
            assert client.post('/api/v2/auth/logout',json={},headers=h).status_code==403
        assert client.post('/api/v2/auth/logout',json={},headers=headers).status_code==200
        client.cookies.set(COOKIE,cookie)
        assert client.get('/api/v2/project').status_code==401
        response=client.post('/api/v2/auth/login',json={'username':'operator','password':PASSWORD})
        assert 'httponly' in response.headers['set-cookie'].lower() and 'samesite=strict' in response.headers['set-cookie'].lower()


def test_bearer_transport_and_ambiguous_credentials(secured):
    cfg,store=secured;session=store.login('operator',PASSWORD)
    with TestClient(create_app(cfg['_root']),base_url='http://localhost') as client:
        assert client.get('/api/v2/project',headers={'Authorization':'Bearer '+session['token']}).status_code==200
        assert client.get('/api/v2/project',headers={'Authorization':'Basic '+session['token']}).status_code==401
        signin(client)
        assert client.get('/api/v2/project',headers={'Authorization':'Bearer '+session['token']}).status_code==400


def test_session_expiry_role_changes_and_disable_revoke(secured):
    _,store=secured;session=store.login('operator',PASSWORD)
    now=store.clock();store.clock=lambda:now+3601
    assert store.authenticate(session['token']) is None
    store.clock=lambda:now
    store.set_role('operator','viewer')
    assert store.authenticate(session['token']) is None
    assert store.login('operator',PASSWORD)['user']['role']=='viewer'
    store.revoke_user('operator')
    with pytest.raises(PermissionError):store.login('operator',PASSWORD)


def test_password_reset_rejects_old_credential_and_session(secured):
    _,store=secured;session=store.login('operator',PASSWORD)
    store.reset_password('operator',PASSWORD+' new')
    assert not store.authenticate(session['token'])
    with pytest.raises(PermissionError):store.login('operator',PASSWORD)
    assert store.login('operator',PASSWORD+' new')


def test_login_throttling_and_hashed_storage(secured):
    _,store=secured
    for _ in range(5):
        with pytest.raises(PermissionError):store.login('unknown','invalid')
    with pytest.raises(PermissionError,match='temporarily'):store.login('unknown','invalid')
    session=store.login('operator',PASSWORD)
    with store.connect() as conn:
        dump='\n'.join(conn.iterdump())
    for secret in (PASSWORD,session['token'],session['csrf']):assert secret not in dump
    assert hashed(session['token']) in dump


def test_store_permissions_symlinks_hardlinks_and_workspace_binding(secured,tmp_path):
    cfg,store=secured
    store.path.chmod(0o644)
    with pytest.raises(ValueError,match='owner-only'):SecurityStore(cfg['_root'])
    store.path.chmod(0o600)
    hard=tmp_path/'hard';os.link(store.path,hard)
    with pytest.raises(ValueError,match='hardlinks'):SecurityStore(cfg['_root'])
    hard.unlink()
    other=workspace(tmp_path/'other');folder=Path(other['_root'])/'.sourceroi/security';folder.mkdir(parents=True,mode=0o700)
    import shutil
    shutil.copy2(store.path,folder/'identity.sqlite3')
    with pytest.raises(ValueError,match='wrong workspace'):SecurityStore(other['_root'])
    (folder/'identity.sqlite3').unlink();(folder/'identity.sqlite3').symlink_to(store.path)
    with pytest.raises(ValueError):SecurityStore(other['_root'])


def test_provisioned_workspace_cannot_silently_downgrade(secured):
    cfg,_=secured
    with pytest.raises(ValueError,match='downgrade'):create_app(cfg['_root'],authenticated=False)


def make_plan(client,cfg,headers):
    snapshot=client.post('/api/v2/data-ci/freeze',json={},headers=headers).json()['snapshot_id']
    (Path(cfg['_root'])/'sources/policy/returns.json').write_text('{"return_days": 14}')
    response=client.post('/api/v2/knowledge/plan',json={'snapshot_id':snapshot,'intent':{'expected_tasks':['returns'],'protected_tasks':['warranty'],'declared_by':'Fixture source owner declaration, not authenticated owner approval','rationale':'Authored security test'}},headers=headers)
    assert response.status_code==200,response.text
    return response.json()


def review_body(spec):return {'specification':spec,'decisions':{'rationale':'Authored test review only','expected_changes':{'returns':'14'},'protected_tasks':['warranty'],'expected_evidence':{'returns':[{'document_id':'policy::returns.json','quote':'14'}]}}}


def test_authenticated_approval_bound_to_server_plan_identity_and_single_use(secured):
    cfg,store=secured;app=create_app(cfg['_root'])
    with TestClient(app,base_url='http://localhost') as operator,TestClient(app,base_url='http://localhost') as reviewer:
        spec=make_plan(operator,cfg,signin(operator));headers=signin(reviewer,'reviewer')
        body=review_body(spec);body['decisions']['reviewer']='admin'
        assert reviewer.post('/api/v2/knowledge/review',json=body,headers=headers).status_code==403
        body['decisions'].pop('reviewer');response=reviewer.post('/api/v2/knowledge/review',json=body,headers=headers)
        assert response.status_code==200,response.text
        approval=response.json();validate_review(spec,approval)
        assert approval['reviewer']=='reviewer' and approval['authenticated_identity']['name']=='reviewer'
        assert approval['authenticated_identity']['workspace']==store.binding
        forged=deepcopy(approval);forged['reviewer']='admin'
        with pytest.raises(ValueError):store.consume_approval(forged,spec)
        store.consume_approval(approval,spec)
        with pytest.raises(ValueError,match='already consumed'):store.consume_approval(approval,spec)


def test_stale_review_rejected_and_unregistered_plan_rejected(secured):
    cfg,store=secured;app=create_app(cfg['_root'])
    with TestClient(app,base_url='http://localhost') as operator,TestClient(app,base_url='http://localhost') as reviewer:
        spec=make_plan(operator,cfg,signin(operator));headers=signin(reviewer,'reviewer')
        fake=deepcopy(spec);fake['id']='forged'
        assert reviewer.post('/api/v2/knowledge/review',json=review_body(fake),headers=headers).status_code==400
        (Path(cfg['_root'])/'sources/policy/returns.json').write_text('{"return_days": 99}')
        response=reviewer.post('/api/v2/knowledge/review',json=review_body(spec),headers=headers)
        assert response.status_code==400 and 'Stale' in response.text


@pytest.mark.parametrize('path',sorted(__import__('sourceroi.live.security',fromlist=['IdentityBoundary']).IdentityBoundary.GENERATION))
def test_no_secure_generation_or_client_semantic_review_bypass(secured,path,monkeypatch):
    cfg,_=secured
    monkeypatch.setattr('sourceroi.live.engine.run_chat',lambda *args:pytest.fail('No inference'))
    with TestClient(create_app(cfg['_root']),base_url='http://localhost') as client:
        headers=signin(client,'admin')
        response=client.post(path,json={'acknowledge_model_calls':True,'semantic_reviews':{'forged':{'approved':True}},'reviewers':['admin']},headers=headers)
        assert response.status_code==403 and 'execution remains disabled' in response.text


def test_audit_request_correlation_no_secrets(secured):
    cfg,store=secured
    with TestClient(create_app(cfg['_root']),base_url='http://localhost') as client:
        headers=signin(client);cookie=client.cookies.get(COOKIE)
        response=client.get('/api/v2/project?secret=never-log-query')
        with store.connect() as conn:rows=[dict(r) for r in conn.execute('SELECT * FROM audit')]
        assert any(r['request_id']==response.headers['x-request-id'] for r in rows)
        serialized=json.dumps(rows)
        assert all(s not in serialized for s in (PASSWORD,cookie,headers['x-csrf-token'],'never-log-query'))


def test_second_process_startup_preserves_active_and_orphaned_legacy_rows(secured):
    cfg,_=secured;rid=db.begin(cfg,'fixture',[])
    code='from sourceroi.live.api import create_app; import sys; create_app(sys.argv[1])'
    result=subprocess.run([sys.executable,'-c',code,cfg['_root']],capture_output=True,timeout=15)
    assert result.returncode==0,result.stderr.decode()
    assert db.get(cfg,rid)['status']=='running'
    # Starting/restarting the HTTP process is not a lease-recovery algorithm.


def test_identity_store_survives_process_kill_and_new_process_reads_session(secured):
    cfg,store=secured
    code='''import sys,time
from sourceroi.live.security import SecurityStore
s=SecurityStore(sys.argv[1]);s.set_role('operator','viewer');print('committed',flush=True);time.sleep(30)
'''
    process=subprocess.Popen([sys.executable,'-c',code,cfg['_root']],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        assert process.stdout.readline().strip()=='committed'
        process.kill();process.wait(timeout=5)
        assert SecurityStore(cfg['_root']).login('operator',PASSWORD)['user']['role']=='viewer'
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=5)


def test_symlinked_identity_directory_rejected_before_creation(tmp_path):
    cfg=workspace(tmp_path/'project');root=Path(cfg['_root']);(root/'.sourceroi').mkdir()
    other=root/'other';other.mkdir(mode=0o700)
    (root/'.sourceroi/security').symlink_to(other,target_is_directory=True)
    with pytest.raises(ValueError,match='symlinks'):SecurityStore(root,initialize=True)
    assert not list(other.iterdir())


def test_cross_user_logout_only_revokes_calling_session(secured):
    cfg,store=secured;app=create_app(cfg['_root'])
    with TestClient(app,base_url='http://localhost') as one,TestClient(app,base_url='http://localhost') as two:
        h1=signin(one,'operator');signin(two,'reviewer')
        assert one.cookies.get(COOKIE)!=two.cookies.get(COOKIE)
        assert one.post('/api/v2/auth/logout',json={'user':'reviewer'},headers=h1).status_code==200
        assert two.get('/api/v2/auth/session').json()['user']['name']=='reviewer'
        assert one.get('/api/v2/auth/session').status_code==401


def test_role_downgrade_invalidates_unused_review_receipt(secured):
    cfg,store=secured;app=create_app(cfg['_root'])
    with TestClient(app,base_url='http://localhost') as operator,TestClient(app,base_url='http://localhost') as reviewer:
        spec=make_plan(operator,cfg,signin(operator));headers=signin(reviewer,'reviewer')
        result=reviewer.post('/api/v2/knowledge/review',json=review_body(spec),headers=headers).json()
        store.set_role('reviewer','viewer')
        with pytest.raises(ValueError,match='revoked'):store.consume_approval(result,spec)
        assert reviewer.get('/api/v2/project').status_code==401


def test_expired_approval_and_recomputed_client_identity_fail_closed(secured):
    from sourceroi.live.data_ci import digest
    cfg,store=secured;app=create_app(cfg['_root'])
    with TestClient(app,base_url='http://localhost') as operator,TestClient(app,base_url='http://localhost') as reviewer:
        spec=make_plan(operator,cfg,signin(operator));headers=signin(reviewer,'reviewer')
        approval=reviewer.post('/api/v2/knowledge/review',json=review_body(spec),headers=headers).json()
        forged=deepcopy(approval);forged['authenticated_identity']['name']='admin';forged['id']=digest({k:v for k,v in forged.items() if k!='id'})
        with pytest.raises(ValueError,match='Approval missing'):store.consume_approval(forged,spec)
        now=store.clock();store.clock=lambda:now+3601
        with pytest.raises(ValueError,match='expired'):store.consume_approval(approval,spec)


def test_identity_transaction_process_kill_rolls_back(secured):
    cfg,store=secured
    code='''import sys,time
from sourceroi.live.security import SecurityStore
s=SecurityStore(sys.argv[1])
with s.connect() as c:
 c.execute("UPDATE users SET role='admin' WHERE name='viewer'")
 print('uncommitted',flush=True)
 time.sleep(30)
'''
    process=subprocess.Popen([sys.executable,'-c',code,cfg['_root']],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        assert process.stdout.readline().strip()=='uncommitted'
        process.kill();process.wait(timeout=5)
        assert SecurityStore(cfg['_root']).login('viewer',PASSWORD)['user']['role']=='viewer'
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=5)


def test_concurrent_receipt_consumption_is_atomic(secured):
    from concurrent.futures import ThreadPoolExecutor
    cfg,store=secured;app=create_app(cfg['_root'])
    with TestClient(app,base_url='http://localhost') as operator,TestClient(app,base_url='http://localhost') as reviewer:
        spec=make_plan(operator,cfg,signin(operator));h=signin(reviewer,'reviewer')
        approval=reviewer.post('/api/v2/knowledge/review',json=review_body(spec),headers=h).json()
    def consume(_):
        try:store.consume_approval(approval,spec);return 'consumed'
        except ValueError:return 'rejected'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(consume,range(2)))
    assert sorted(results)==['consumed','rejected']


def test_client_cannot_choose_role_at_login_or_extend_session(secured):
    cfg,_=secured
    with TestClient(create_app(cfg['_root']),base_url='http://localhost') as client:
        response=client.post('/api/v2/auth/login',json={'username':'viewer','password':PASSWORD,'role':'admin','expires_at':99999999999})
        assert response.json()['user']['role']=='viewer'
        assert response.json()['expires_at']<time.time()+3601


def test_cli_provisions_private_store_and_refuses_piped_passwords(tmp_path,monkeypatch,capsys):
    from sourceroi.live.cli import main
    cfg=workspace(tmp_path/'project')
    assert main(['--project',cfg['_root'],'auth-init'])==0
    monkeypatch.setattr(sys.stdin,'isatty',lambda:False)
    assert main(['--project',cfg['_root'],'auth-add-user','--user','operator','--role','operator'])!=0
    assert 'interactive terminal' in capsys.readouterr().err


def test_partial_provisioning_cannot_fall_back_to_open_service(tmp_path):
    cfg=workspace(tmp_path/'project')
    (Path(cfg['_root'])/'.sourceroi/security').mkdir(parents=True,mode=0o700)
    with pytest.raises(ValueError,match='Initialize'):create_app(cfg['_root'])


def test_source_edit_after_review_invalidates_receipt_before_consumption(secured):
    cfg,store=secured;app=create_app(cfg['_root'])
    with TestClient(app,base_url='http://localhost') as operator,TestClient(app,base_url='http://localhost') as reviewer:
        spec=make_plan(operator,cfg,signin(operator));h=signin(reviewer,'reviewer')
        approval=reviewer.post('/api/v2/knowledge/review',json=review_body(spec),headers=h).json()
    (Path(cfg['_root'])/'sources/policy/returns.json').write_text('{"return_days": 77}')
    with pytest.raises(ValueError,match='Stale'):store.consume_approval(approval,spec)
    with store.connect() as conn:assert conn.execute('SELECT used FROM approvals WHERE id=?',(approval['id'],)).fetchone()[0]==0


def test_remote_peer_cannot_bypass_loopback_with_host_or_forwarded_headers(secured):
    import asyncio
    from sourceroi.live.security import IdentityBoundary
    _,store=secured
    async def scenario():
        called=[];sent=[]
        async def app(*args):called.append(True)
        async def receive():return {'type':'http.request','body':b''}
        async def send(message):sent.append(message)
        await IdentityBoundary(app,store)({'type':'http','method':'GET','path':'/api/v2/health','client':('198.51.100.10',4321),
            'headers':[(b'host',b'localhost'),(b'x-forwarded-for',b'127.0.0.1')]},receive,send)
        assert not called and sent[0]['status']==403
    asyncio.run(scenario())
