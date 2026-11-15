"""Fixture-only provider reservations attached to the EXISTING durable jobs.

This is not a real generation authorization. No URL/command/model is selectable.
Provider token numbers are synthetic fixture reports, never observed LLM usage.
"""
import json
from pathlib import Path
import secrets
import sys
import tempfile
from .data_ci import digest


def install(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS fixture_authorizations(id TEXT PRIMARY KEY,actor TEXT NOT NULL,spec TEXT NOT NULL,max_attempts INTEGER NOT NULL,expires REAL NOT NULL,used INTEGER NOT NULL,revoked INTEGER NOT NULL,scope TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS job_attempts(id TEXT PRIMARY KEY,job TEXT NOT NULL,task TEXT NOT NULL,version TEXT NOT NULL,state TEXT NOT NULL,request_hash TEXT NOT NULL,request TEXT NOT NULL,response TEXT,usage TEXT,created REAL NOT NULL,updated REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS job_native_fixture_evidence(attempt TEXT PRIMARY KEY,evidence TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS job_runtime_artifacts(attempt TEXT PRIMARY KEY,operation_id TEXT NOT NULL);
    ''')


def authorize(jobs,actor,spec,*,max_attempts=8,max_seconds=60):
    if type(max_attempts) is not int or not 1<=max_attempts<=40 or type(max_seconds) is not int or not 1<=max_seconds<=60:raise ValueError('Fixture authorization requires 1..40 attempts, 1..60 seconds, zero retries/spend')
    jobs.store.registered_plan(spec);ident=secrets.token_hex(16)
    with jobs.store.connect() as c:
        jobs._actor(c,actor)
        c.execute('INSERT INTO fixture_authorizations VALUES (?,?,?,?,?,0,0,?)',(ident,actor['id'],spec['id'],max_attempts,jobs.store.clock()+max_seconds,'deterministic_fixture_only'))
    jobs.store.audit('fixture_authorized',actor['id']);return {'id':ident,'scope':'deterministic_fixture_only','max_attempts':max_attempts,'max_seconds':max_seconds,'retries':0,'spend_usd':0,'real_generation_authorized':False}


def permission(c,jobs,actor,spec,auth_id,*,consumed):
    row=c.execute('SELECT * FROM fixture_authorizations WHERE id=?',(auth_id,)).fetchone()
    if not row or row['actor']!=actor['id'] or row['spec']!=spec['id'] or row['scope']!='deterministic_fixture_only' or row['revoked'] or bool(row['used'])!=consumed or row['expires']<=jobs.store.clock():raise ValueError('Invalid, revoked, expired or used fixture authorization')
    return row


def attempt(jobs,j,task_id,version,body,answer,citations,mode):
    aid=secrets.token_hex(16);p=j['payload'];now=jobs.store.clock()
    wire={'fixture_authorization':p['fixture_authorization'],'owner_fence':j['fence'],'job_id':j['id'],'attempt_id':aid,'task_id':task_id,'mode':mode,'answer':answer,'citations':citations,'body':body}
    encoded=json.dumps(wire,allow_nan=False)
    if len(encoded)>1024*1024:raise ValueError('Fixture request exceeds resource limit')
    with jobs.store.connect() as c:
        owned=jobs._owned(c,j['id'],j['worker'],j['fence'])
        if owned['state']!='RUNNING':raise ValueError('Fixture dispatch cancelled')
        jobs._actor(c,{'id':j['actor']},p.get('actor_revision',0));jobs._approval(c,p['approval'],p['spec'],consumed=True)
        auth=permission(c,jobs,{'id':j['actor']},p['spec'],p['fixture_authorization'],consumed=True)
        if c.execute('SELECT COUNT(*) FROM job_attempts WHERE job=?',(j['id'],)).fetchone()[0]>=auth['max_attempts']:raise ValueError('Fixture provider attempt cap exceeded')
        c.execute('INSERT INTO job_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?)',(aid,j['id'],task_id,version,'RESERVED',digest(wire),encoded,None,None,now,now))
    try:
        from .runtime_resources import scratch
        with scratch() as (root,owner_fd):
            with jobs.store.connect() as c:
                jobs._owned(c,j['id'],j['worker'],j['fence'])
                c.execute('INSERT INTO job_runtime_artifacts VALUES (?,?)',(aid,root.parent.name))
            (root/'request.json').write_text(encoded)
            permits=root/'permits';permits.mkdir(mode=0o700)
            native_wire=json.dumps(body,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
            with (permits/aid).open('xb') as permit:permit.write(native_wire);permit.flush();__import__('os').fsync(permit.fileno())
            with jobs.store.connect() as c:
                owned=jobs._owned(c,j['id'],j['worker'],j['fence'])
                if owned['state']!='RUNNING':raise ValueError('Fixture cancelled before dispatch')
                permission(c,jobs,{'id':j['actor']},p['spec'],p['fixture_authorization'],consumed=True)
                c.execute("UPDATE job_attempts SET state='DISPATCHED',updated=? WHERE id=?",(jobs.store.clock(),aid))
            from .parser_boundary import supervise
            remaining=min(2,max(.001,owned['deadline']-jobs.store.clock()),max(.001,auth['expires']-jobs.store.clock()))
            def cancelled():
                import sqlite3
                try:
                    with sqlite3.connect(jobs.store.path,timeout=.02) as check:
                        live=check.execute('SELECT state,worker,fence,lease FROM jobs WHERE id=?',(j['id'],)).fetchone()
                    return live is None or live[0]!='RUNNING' or live[1]!=j['worker'] or live[2]!=j['fence'] or live[3]<=jobs.store.clock()
                except sqlite3.Error:return True
            supervise([sys.executable,'-m','sourceroi.live.fixture_provider_worker'],root,wall=remaining,sandbox=True,protected_root=jobs.store.root,owner_fd=owner_fd,cancel_check=cancelled)
            raw=(root/'response.json').read_text()
            if len(raw)>1024*1024:raise ValueError('Fixture terminal response too large')
            with jobs.store.connect() as c:
                jobs._owned(c,j['id'],j['worker'],j['fence'])
                c.execute('UPDATE job_attempts SET response=?,updated=? WHERE id=?',(raw,jobs.store.clock(),aid))
            from .native_accounting import inspect_native
            captured_native=json.loads((root/'native-response.json').read_text())
            reported=json.loads(captured_native['body']).get('usage')
            native=inspect_native(root,{'max_calls':1},[{'request_id':aid,'artifact':'native-request.json'}],[{'request_id':aid,'artifact':'native-response.json','usage':reported}],[])
            evidence={'fixture_only':True,'authorization_identity':p['fixture_authorization'],'owner_fence':j['fence'],'request':json.loads((root/'native-request.json').read_text()),'response':json.loads((root/'native-response.json').read_text()),'records':[json.loads(line) for line in (root/'native-events.jsonl').read_text().splitlines()],'reconciliation':native}
            with jobs.store.connect() as c:
                jobs._owned(c,j['id'],j['worker'],j['fence'])
                c.execute('INSERT INTO job_native_fixture_evidence VALUES (?,?)',(aid,json.dumps(evidence)))
            response=json.loads(raw)
            if native['failures'] or native['confirmed_completions']!=1:raise ValueError('Native protocol fixture reconciliation failed')
        if response.get('attempt_id')!=aid or response.get('task_id')!=task_id or response.get('fixture') is not True or response.get('child_calls')!=0:raise ValueError('Fixture provider correlation/untracked child failure')
        usage=response.get('usage')
        if not isinstance(usage,dict) or set(usage)!={'prompt_tokens','completion_tokens'} or any(type(v) is not int or v<0 for v in usage.values()):raise ValueError('Fixture provider usage unknown')
        with jobs.store.connect() as c:
            jobs._owned(c,j['id'],j['worker'],j['fence'])
            c.execute("UPDATE job_attempts SET state='COMPLETED',response=?,usage=?,updated=? WHERE id=?",(json.dumps(response),json.dumps(usage),jobs.store.clock(),aid))
        return {'choices':[{'message':{'content':json.dumps({'answer':response['answer'],'citations':response['citations']})},'finish_reason':'stop'}],'usage':usage}
    except BaseException as exc:
        with jobs.store.connect() as c:
            try:jobs._owned(c,j['id'],j['worker'],j['fence'])
            except ValueError:pass  # Lost owners leave reconciliation to recover().
            else:c.execute("UPDATE job_attempts SET state='UNKNOWN',updated=? WHERE id=? AND state!='COMPLETED'",(jobs.store.clock(),aid))
        raise ValueError('Fixture provider outcome incomplete or unknown; no retry') from exc


def reconcile(jobs,j):
    with jobs.store.connect() as c:
        rows=[dict(r) for r in c.execute('SELECT * FROM job_attempts WHERE job=? ORDER BY created,id',(j['id'],))]
        permit=c.execute('SELECT max_attempts FROM fixture_authorizations WHERE id=?',(j['payload']['fixture_authorization'],)).fetchone()
    if not permit or len(rows)>permit[0]:raise ValueError('Fixture attempt budget reconciliation failed')
    evidence=[]
    for row in rows:
        if row['state']!='COMPLETED' or not row['response'] or not row['usage']:raise ValueError('Fixture attempt incomplete')
        request=json.loads(row['request']);response=json.loads(row['response']);usage=json.loads(row['usage'])
        if digest(request)!=row['request_hash'] or request['attempt_id']!=row['id'] or request['task_id']!=row['task'] or response.get('attempt_id')!=row['id'] or response.get('task_id')!=row['task'] or response.get('child_calls')!=0 or response.get('fixture') is not True or response.get('usage')!=usage:raise ValueError('Fixture request/terminal reconciliation mismatch')
        with jobs.store.connect() as c:captured=c.execute('SELECT evidence FROM job_native_fixture_evidence WHERE attempt=?',(row['id'],)).fetchone()
        if captured is None:raise ValueError('Native protocol fixture evidence missing')
        native=json.loads(captured[0])
        if native['authorization_identity']!=j['payload']['fixture_authorization'] or native['request']!=request['body'] or native['reconciliation']['failures'] or native['reconciliation']['confirmed_completions']!=1:raise ValueError('Native fixture authorization/body reconciliation mismatch')
        decoded=json.loads(native['response']['body']);answer=json.loads(decoded['choices'][0]['message']['content'])
        if answer!={'answer':response['answer'],'citations':response['citations']} or decoded['usage']!={**usage,'total_tokens':sum(usage.values())}:raise ValueError('Native fixture terminal/body reconciliation mismatch')
        evidence.append({'id':row['id'],'request':row['request_hash'],'terminal':digest(response),'usage':digest(usage),'native_fixture':digest(native)})
    return {'status':'RECONCILED_FIXTURE','version':2,'attempts':evidence,'seal':digest({'job':j['id'],'attempts':evidence})}


def execute(jobs,j):
    from copy import deepcopy
    from .config import read_config,secure_path
    from .ingest import load_benchmark,scan_sources
    from .engine import evaluate_variant
    from .assurance import execute as release
    p=j['payload'];root=jobs.store.root
    before=read_config(secure_path(root,'.sourceroi/snapshots/'+p['identity']['snapshot']));after=read_config(root)
    def callback(cfg,selected):
        version='baseline' if cfg['_root']==before['_root'] else 'candidate'
        rows=[];metrics={};docs,chunks=scan_sources(cfg);manifest={d['id']:d['fingerprint'] for d in docs}
        frozen={t['id']:t for t in load_benchmark(cfg)}
        for task in selected:
            jobs.heartbeat(j['id'],j['worker'],j['fence'])
            value=p['fixture_responses'][version][task['id']]
            def transport(url,body,timeout,*args):
                import re
                ids=re.findall(r'\[SOURCE_ID: ([^\]]+)\]',body['messages'][-1]['content'])
                return attempt(jobs,j,task['id'],version,body,value,ids,p['fixture_mode'])
            runtime=deepcopy(cfg);runtime['model']={**runtime['model'],'name':'deterministic-fixture-NO-MODEL','local_only':True,'base_url':'http://127.0.0.1:1/v1','context_tokenizer':None,'compact_source_ids':False}
            runtime['_experiment_transport']=transport;runtime['_strict_analysis_isolation']=True
            runtime['settings']={**runtime.get('settings',{}),'release_policy':'strict_grounded'}
            result=evaluate_variant(runtime,[frozen[task['id']]],chunks,[]);row=result['tasks'][0]
            row.update(knowledge_manifest=manifest,knowledge_version=digest(manifest),usage_source='fixture_reported' if row.get('usage_source')=='provider_reported' else row.get('usage_source'))
            rows.append(row);metrics=result['metrics']
            jobs.checkpoint(j['id'],j['worker'],j['fence'],{'stage':'fixture_task_results','version':version,'rows':rows,'new_real_generations':0})
        return {'tasks':rows,'metrics':metrics}
    report=release(before,after,p['spec'],approval=p['approval'],callback=callback,max_calls=400,max_seconds=p['max_seconds'],persist=False,policy='strict_grounded')
    with jobs.store.connect() as c:attempts=[dict(r) for r in c.execute('SELECT * FROM job_attempts WHERE job=? ORDER BY created,id',(j['id'],))]
    if any(r['state']!='COMPLETED' for r in attempts) or report['verdict']=='INCONCLUSIVE':raise ValueError('Fixture reconciliation incomplete')
    verdict=report['verdict'] if report['verdict']!='ACCEPT' else 'REVIEW'
    return {'kind':'fixture_release','fixture_only':True,'verdict':verdict,'release':report,'provider_attempts':len(attempts),'new_real_generations':0,'usage_source':'fixture_reported','semantic_review':'PENDING','reconciliation':reconcile(jobs,j),'identity':p['identity']}
