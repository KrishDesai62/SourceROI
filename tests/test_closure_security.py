"""Additive identity migration and explicit authority, no independent humans."""
from pathlib import Path
import sqlite3
import pytest
from examples.knowledge_change.demo import workspace
from sourceroi.live.security import SecurityStore
from sourceroi.live.api import create_app
from sourceroi.live.cli import main
from sourceroi.live.workspace_lock import workspace_lock


def old_fixture(tmp_path):
    cfg=workspace(tmp_path/'project');store=SecurityStore(cfg['_root'],initialize=True);store.add_user('reviewer','Development-only migration password','reviewer')
    session=store.login('reviewer','Development-only migration password')
    with store.connect() as c:c.execute('UPDATE metadata SET version=1')
    return cfg,store,session


def test_upgrade_requires_explicit_quiescence_and_revokes_sessions(tmp_path):
    cfg,store,session=old_fixture(tmp_path)
    with pytest.raises(ValueError,match='auth-migrate'):create_app(cfg['_root'])
    with workspace_lock(cfg['_root']):assert main(['--project',cfg['_root'],'auth-migrate'])==2
    assert main(['--project',cfg['_root'],'auth-migrate'])==0
    current=SecurityStore(cfg['_root']);assert not current.authenticate(session['token'])
    assert current.login('reviewer','Development-only migration password')
    with current.connect() as c:assert c.execute('SELECT version FROM metadata').fetchone()[0]==2
    with pytest.raises(ValueError,match='downgrade'):create_app(cfg['_root'],authenticated=False)


def test_failed_upgrade_rolls_back_version_and_sessions(tmp_path):
    cfg,store,session=old_fixture(tmp_path)
    with store.connect() as c:c.execute("CREATE TRIGGER migration_failure BEFORE UPDATE ON metadata BEGIN SELECT RAISE(ABORT,'fixture interrupted upgrade'); END")
    with pytest.raises(sqlite3.IntegrityError,match='interrupted'):SecurityStore(cfg['_root'],migrate=True)
    with store.connect() as c:
        assert c.execute('SELECT version FROM metadata').fetchone()[0]==1
        assert c.execute('SELECT revoked FROM sessions').fetchone()[0]==0


def test_new_approval_explicitly_has_no_owner_independence_or_generation_authority(tmp_path):
    cfg=workspace(tmp_path/'project');store=SecurityStore(cfg['_root'],initialize=True);store.add_user('reviewer','Development-only authority password','reviewer')
    actor=store.login('reviewer','Development-only authority password')['user']
    record=store.bind_approval({'id':'fixture','spec_id':'fixture'},actor)
    assert record['authority_basis']['source_owner_delegation']=='UNVERIFIED'
    assert record['authority_basis']['external_independence']=='UNVERIFIED'
    assert record['authority_basis']['generation_permission'] is False
    assert record['authority_basis']['release_permission'] is False


def test_migration_fences_pending_jobs_and_attempts(tmp_path):
    cfg,store,session=old_fixture(tmp_path)
    # Initialize the additive job tables before marking this authored store v1.
    with store.connect() as c:c.execute('UPDATE metadata SET version=2')
    from sourceroi.live.durable_jobs import Jobs
    Jobs(store)
    with store.connect() as c:
        uid=c.execute('SELECT id FROM users').fetchone()[0]
        c.execute("INSERT INTO jobs(id,actor,operation,key,request_hash,payload,state,worker,fence,lease,deadline,created,updated) VALUES ('fixture-job',?,'fixture_release','fixture-key','fixture','{}','RUNNING','fixture-worker',3,99999999999,99999999999,0,0)",(uid,))
        c.execute('UPDATE metadata SET version=1')
    SecurityStore(cfg['_root'],migrate=True)
    with store.connect() as c:
        row=c.execute("SELECT state,fence,reason FROM jobs WHERE id='fixture-job'").fetchone()
        assert row['state']=='INCONCLUSIVE' and row['fence']==4 and 'reconciliation' in row['reason']


def test_existing_native_reconciler_validates_durable_fixture_evidence(tmp_path):
    # Use the existing reusable authored job fixture through its wrapped factory.
    from test_phase2_jobs import setup
    from test_fixture_release_semantics import prepared
    data=setup.__wrapped__(tmp_path);cfg,store,jobs,*_=data;j,_=prepared(data)
    assert jobs.run_one('closure-native-fixture')['state']=='COMPLETED'
    with store.connect() as c:rows=c.execute('SELECT evidence FROM job_native_fixture_evidence').fetchall()
    import json
    assert rows and all(not json.loads(r[0])['reconciliation']['failures'] for r in rows)
    assert all(json.loads(r[0])['fixture_only'] is True for r in rows)


def test_durable_cancellation_stops_actual_dispatched_fixture(tmp_path):
    from test_phase2_jobs import setup
    from test_fixture_release_semantics import prepared
    from concurrent.futures import ThreadPoolExecutor
    import time
    data=setup.__wrapped__(tmp_path);cfg,store,jobs,actor,*_=data;j,_=prepared(data,mode='timeout')
    with ThreadPoolExecutor(max_workers=1) as pool:
        result=pool.submit(jobs.run_one,'cancelled-native-fixture')
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            with store.connect() as c:row=c.execute('SELECT state FROM job_attempts WHERE job=?',(j['id'],)).fetchone()
            if row and row[0]=='DISPATCHED':break
            time.sleep(.02)
        assert row and row[0]=='DISPATCHED'
        requested=jobs.cancel(j['id'],actor);assert requested['state']=='CANCEL_REQUESTED'
        end=result.result(timeout=5);assert end['state']=='INCONCLUSIVE'
        assert jobs.run_one('no-retry-fixture-worker') is None


def test_native_fixture_permit_tampering_is_unknown_not_retried(tmp_path,monkeypatch):
    from test_phase2_jobs import setup
    from test_fixture_release_semantics import prepared
    from sourceroi.live import parser_boundary as boundary
    data=setup.__wrapped__(tmp_path);cfg,store,jobs,*_=data;j,_=prepared(data)
    original=boundary.supervise
    def corrupt(command,cwd,**kwargs):
        if 'sourceroi.live.fixture_provider_worker' in command:
            next((Path(cwd)/'permits').iterdir()).write_bytes(b'wrong wire body')
        return original(command,cwd,**kwargs)
    monkeypatch.setattr(boundary,'supervise',corrupt)
    assert jobs.run_one('permit-tamper-fixture')['state']=='INCONCLUSIVE'
    with store.connect() as c:
        rows=c.execute('SELECT state FROM job_attempts').fetchall()
        assert len(rows)==1 and rows[0][0]=='UNKNOWN'
