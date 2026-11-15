"""Durable offline orchestration. No provider imports or real generation route.

Approval and job rows share the private identity database: one transaction binds
consumption to creation. Leases fence commits, never authorize redispatch.
"""
import json
import re
import secrets
import time
from .data_ci import digest
from .security import SecurityStore

TERMINAL={'COMPLETED','FAILED','CANCELLED','INCONCLUSIVE'}
TRANSITIONS={'CREATED':{'QUEUED','CANCELLED'},'QUEUED':{'CLAIMED','CANCELLED'},'CLAIMED':{'RUNNING','CANCEL_REQUESTED','CANCELLED','FAILED','INCONCLUSIVE'},'RUNNING':{'CANCEL_REQUESTED','COMPLETED','FAILED','INCONCLUSIVE'},'CANCEL_REQUESTED':{'CANCELLED','INCONCLUSIVE'}}

class JobConflict(ValueError):pass

class Jobs:
    def __init__(self,store):
        self.store=store
        with store.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS job_schema(version INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,actor TEXT NOT NULL,operation TEXT NOT NULL,key TEXT NOT NULL,request_hash TEXT NOT NULL,payload TEXT NOT NULL,state TEXT NOT NULL,worker TEXT,fence INTEGER NOT NULL DEFAULT 0,lease REAL,deadline REAL NOT NULL,reservation TEXT,partial TEXT,result TEXT,reason TEXT,created REAL NOT NULL,updated REAL NOT NULL,UNIQUE(actor,operation,key));
            CREATE TABLE IF NOT EXISTS job_events(id INTEGER PRIMARY KEY,job TEXT NOT NULL,at REAL NOT NULL,state TEXT NOT NULL,reason TEXT,fence INTEGER NOT NULL);
            ''')
            if not c.in_transaction:c.execute('BEGIN IMMEDIATE')
            if not c.execute('SELECT 1 FROM job_schema').fetchone():c.execute('INSERT INTO job_schema VALUES (1)')
            if c.execute('SELECT version FROM job_schema').fetchone()[0]!=1:raise ValueError('Incompatible durable job schema')
            from .fixture_execution import install
            install(c)

    def _event(self,c,j,state,reason=None):
        c.execute('INSERT INTO job_events(job,at,state,reason,fence) VALUES (?,?,?,?,?)',(j['id'],self.store.clock(),state,reason,j['fence']))

    def _move(self,c,j,state,reason=None,**fields):
        if state not in TRANSITIONS.get(j['state'],set()):raise ValueError('Invalid job transition')
        fields.update(state=state,updated=self.store.clock(),reason=reason)
        c.execute('UPDATE jobs SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',(*fields.values(),j['id']))
        self._event(c,{**j,**fields},state,reason)

    def _actor(self,c,actor,revision=None):
        row=c.execute('SELECT * FROM users WHERE id=? AND enabled=1',(actor['id'],)).fetchone()
        if not row or row['role'] not in ('operator','admin'):raise ValueError('Active operator role required')
        current=c.execute('SELECT revision FROM identity_revisions WHERE user_id=?',(actor['id'],)).fetchone()
        if revision is not None and revision!=(current[0] if current else 0):raise ValueError('Actor authority changed since submission')
        return row

    def _approval(self,c,approval,spec,*,consumed):
        from .assurance import validate_review
        validate_review(spec,approval)
        row=c.execute('SELECT a.*,u.role,u.enabled FROM approvals a JOIN users u ON u.id=a.actor WHERE a.id=? AND a.spec=?',(approval['id'],spec['id'])).fetchone()
        revoked=c.execute('SELECT 1 FROM approval_revocations WHERE id=?',(approval['id'],)).fetchone()
        if not row or revoked or bool(row['used'])!=consumed or row['expires']<=self.store.clock() or not row['enabled'] or row['role'] not in ('reviewer','admin'):raise ValueError('Approval expired, revoked, consumed or missing')
        return row

    def _inputs(self,spec,approval):
        from .assurance import validate_release_inputs
        from .config import read_config,secure_path
        snapshot=self.store.registered_plan(spec)
        before=read_config(secure_path(self.store.root,'.sourceroi/snapshots/'+snapshot));after=read_config(self.store.root)
        validate_release_inputs(before,after,spec,approval)
        from .release_policy import resolve
        return {'workspace':self.store.binding,'snapshot':snapshot,'plan':spec['id'],
                'versions':{k:spec[k] for k in ('baseline_sources','candidate_sources','baseline_configuration','candidate_configuration','test_set_version')},'policy':resolve(after)}

    def submit(self,actor,key,spec,approval,*,operation='offline_release_preflight',max_seconds=60,fixture_authorization=None,fixture_responses=None,fixture_mode='valid'):
        if operation not in ('offline_release_preflight','fixture_release'):raise ValueError('Generation jobs disabled; separate authorization and Phase 3 gates required')
        if operation=='fixture_release':
            from .ingest import load_benchmark
            from .config import read_config
            ids={t['id'] for t in load_benchmark(read_config(self.store.root))}
            if not fixture_authorization or not isinstance(fixture_responses,dict) or set(fixture_responses)!={'baseline','candidate'} or any(not isinstance(rows,dict) or set(rows)!=ids or any(not isinstance(v,(str,int,float,bool)) for v in rows.values()) for rows in fixture_responses.values()):raise ValueError('Fixture authorization and complete frozen-task response map required')
            if fixture_mode not in ('valid','missing_usage','timeout','partial','child_call','failure'):raise ValueError('Unsupported fixture mode')
        elif fixture_authorization or fixture_responses:raise ValueError('Fixture fields require fixture_release')
        if not re.fullmatch(r'[A-Za-z0-9_.-]{8,128}',key):raise ValueError('Idempotency key must be 8..128 simple characters')
        if type(max_seconds) is not int or not 1<=max_seconds<=300:raise ValueError('Job deadline must be 1..300 seconds')
        # Compute live identities even on duplicate requests: changed inputs are not
        # silently mapped to an earlier job. No provider is called.
        try:identity=self._inputs(spec,approval)
        except ValueError:
            self.store.audit('job_submission_rejected',actor.get('id'),409);raise
        with self.store.connect() as c:
            self._actor(c,actor)
            revision=c.execute('SELECT revision FROM identity_revisions WHERE user_id=?',(actor['id'],)).fetchone()
            actor_revision=revision[0] if revision else 0
        payload={'actor_revision':actor_revision,'operation':operation,'spec':spec,'approval':approval,'identity':identity,'max_seconds':max_seconds,'generation_authorization':None}
        if operation=='fixture_release':payload.update(fixture_authorization=fixture_authorization,fixture_responses=fixture_responses,fixture_mode=fixture_mode)
        request_hash=digest(payload);now=self.store.clock();jid=secrets.token_hex(16)
        with self.store.connect() as c:
            self._actor(c,actor,actor_revision)
            old=c.execute('SELECT * FROM jobs WHERE actor=? AND operation=? AND key=?',(actor['id'],operation,key)).fetchone()
            if old:
                if old['request_hash']!=request_hash:raise JobConflict('Idempotency key payload/identity conflict')
                return self._decode(old)
            self._approval(c,approval,spec,consumed=False)
            if operation=='fixture_release':
                from .fixture_execution import permission
                permission(c,self,actor,spec,fixture_authorization,consumed=False)
            if c.execute("SELECT COUNT(*) FROM jobs WHERE state NOT IN ('COMPLETED','FAILED','CANCELLED','INCONCLUSIVE')").fetchone()[0]>=100:raise ValueError('Workspace queue limit reached')
            c.execute('INSERT INTO jobs(id,actor,operation,key,request_hash,payload,state,deadline,created,updated) VALUES (?,?,?,?,?,?,?,?,?,?)',(jid,actor['id'],operation,key,request_hash,json.dumps(payload),'CREATED',now+max_seconds,now,now))
            j=dict(c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone());self._event(c,j,'CREATED')
            self._move(c,j,'QUEUED','approved_offline_only')
            c.execute('UPDATE approvals SET used=1 WHERE id=?',(approval['id'],))
            if operation=='fixture_release':c.execute('UPDATE fixture_authorizations SET used=1 WHERE id=?',(fixture_authorization,))
            c.execute('INSERT INTO audit(at,event,actor,status) VALUES (?,?,?,?)',(now,'job_submitted',actor['id'],202))
            result=c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
        return self._decode(result)

    def _decode(self,row):
        if not row:return None
        result=dict(row)
        for k in ('payload','partial','result'):
            if result[k] is not None:result[k]=json.loads(result[k])
        if digest(result['payload'])!=result['request_hash']:raise ValueError('Job payload identity mismatch')
        return result

    def get(self,jid):
        with self.store.connect() as c:return self._decode(c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone())

    def events(self,jid):
        with self.store.connect() as c:return [dict(r) for r in c.execute('SELECT * FROM job_events WHERE job=? ORDER BY id',(jid,))]

    def recover(self):
        now=self.store.clock();changed=[]
        with self.store.connect() as c:
            rows=c.execute("SELECT * FROM jobs WHERE state IN ('QUEUED','CLAIMED','RUNNING','CANCEL_REQUESTED')").fetchall()
            for row in rows:
                j=dict(row)
                if j['state']=='QUEUED':
                    if j['deadline']<=now:self._move(c,j,'CANCELLED','deadline_before_claim');changed.append(j['id'])
                elif j['lease']<=now or j['deadline']<=now:
                    uncertain=bool(j['reservation'])
                    self._move(c,j,'INCONCLUSIVE' if uncertain else 'CANCELLED','owner_lost_unknown_outcome' if uncertain else 'owner_lost_before_reservation',fence=j['fence']+1)
                    c.execute("UPDATE job_attempts SET state='UNKNOWN',updated=? WHERE job=? AND state IN ('RESERVED','DISPATCHED')",(now,j['id']))
                    changed.append(j['id'])
        return changed

    def claim(self,worker,*,lease_seconds=15):
        if not isinstance(worker,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{8,128}',worker):raise ValueError('Unique simple worker identity required')
        if not 1<=lease_seconds<=60:raise ValueError('Lease must be 1..60 seconds')
        self.recover();now=self.store.clock()
        with self.store.connect() as c:
            row=c.execute("SELECT * FROM jobs WHERE state='QUEUED' AND deadline>? ORDER BY created,id LIMIT 1",(now,)).fetchone()
            if not row:return None
            j=dict(row);fence=j['fence']+1
            self._move(c,j,'CLAIMED','atomic_claim',worker=worker,fence=fence,lease=min(now+lease_seconds,j['deadline']))
            return self._decode(c.execute('SELECT * FROM jobs WHERE id=?',(j['id'],)).fetchone())

    def _owned(self,c,jid,worker,fence):
        row=c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
        if not row or row['state'] in TERMINAL or row['worker']!=worker or row['fence']!=fence or row['lease']<=self.store.clock() or row['deadline']<=self.store.clock():raise ValueError('Stale/expired worker ownership')
        return dict(row)

    def heartbeat(self,jid,worker,fence,*,lease_seconds=15):
        if not 1<=lease_seconds<=60:raise ValueError('Lease must be 1..60 seconds')
        with self.store.connect() as c:
            j=self._owned(c,jid,worker,fence)
            c.execute('UPDATE jobs SET lease=?,updated=? WHERE id=?',(min(self.store.clock()+lease_seconds,j['deadline']),self.store.clock(),jid))

    def reserve(self,jid,worker,fence):
        # Offline work reservation, NOT a native generation permit. No real
        # dispatch method exists. A crash from this point is conservatively unknown.
        with self.store.connect() as c:
            j=self._owned(c,jid,worker,fence)
            if j['state']!='CLAIMED' or j['reservation']:raise ValueError('Reservation cannot restart or replay')
            p=json.loads(j['payload']);self._actor(c,{'id':j['actor']},p.get('actor_revision',0));self._approval(c,p['approval'],p['spec'],consumed=True)
            self._move(c,j,'RUNNING','offline_reservation',reservation=secrets.token_hex(16))

    def checkpoint(self,jid,worker,fence,value):
        encoded=json.dumps(value,allow_nan=False)
        if len(encoded)>1024*1024:raise ValueError('Partial result too large')
        with self.store.connect() as c:
            self._owned(c,jid,worker,fence);c.execute('UPDATE jobs SET partial=?,updated=? WHERE id=?',(encoded,self.store.clock(),jid))

    def finish(self,jid,worker,fence,*,state='COMPLETED',result=None):
        if state not in TERMINAL:raise ValueError('Terminal state required')
        if result and result.get('verdict')=='ACCEPT':raise ValueError('Offline orchestration cannot authorize ACCEPT')
        encoded=json.dumps(result,allow_nan=False)
        if len(encoded)>1024*1024:raise ValueError('Result too large')
        with self.store.connect() as c:
            j=self._owned(c,jid,worker,fence)
            if j['state']=='CANCEL_REQUESTED':
                state='INCONCLUSIVE' if j['reservation'] else 'CANCELLED';result={'verdict':'INCONCLUSIVE','usage':None,'reason':'cancelled_after_reservation' if j['reservation'] else 'cancelled_before_reservation'};encoded=json.dumps(result)
            if state=='COMPLETED':
                p=json.loads(j['payload'])
                try:
                    self._actor(c,{'id':j['actor']},p.get('actor_revision',0));self._approval(c,p['approval'],p['spec'],consumed=True)
                    if j['operation']=='fixture_release':
                        from .fixture_execution import permission
                        permission(c,self,{'id':j['actor']},p['spec'],p['fixture_authorization'],consumed=True)
                except ValueError:state='INCONCLUSIVE';encoded=json.dumps({'verdict':'INCONCLUSIVE','usage':None,'reason':'authority_changed_before_commit'})
            self._move(c,j,state,'worker_terminal',result=encoded)

    def cancel(self,jid,actor):
        with self.store.connect() as c:
            live_actor=self._actor(c,actor);row=c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
            if not row:raise ValueError('Unknown job')
            j=dict(row)
            if j['actor']!=actor['id'] and live_actor['role']!='admin':raise ValueError('Job not owned by actor')
            if j['state'] in TERMINAL or j['state']=='CANCEL_REQUESTED':return self._decode(row)
            self._move(c,j,'CANCELLED' if j['state'] in ('CREATED','QUEUED') else 'CANCEL_REQUESTED','operator_cancellation')
        return self.get(jid)

    def run_one(self,worker):
        from .workspace_lock import workspace_lock
        with workspace_lock(self.store.root):
            j=self.claim(worker)
            if not j:return None
            jid=j['id'];fence=j['fence']
            try:
                self._inputs(j['payload']['spec'],j['payload']['approval'])
                self.reserve(jid,worker,fence)
                self.checkpoint(jid,worker,fence,{'stage':'canonical_inputs_checked','generation_attempts':0})
                # Fixed offline operation: no client callback, shell, provider or
                # arbitrary operation import can be supplied through a job.
                result={'kind':'offline_release_preflight','verdict':'INCONCLUSIVE','generation_attempts':0,'usage':None,'semantic_review':'PENDING','reason':'No model execution; execution and Phase 3 gates remain disabled','identity':j['payload']['identity']}
                if j['operation']=='fixture_release':
                    from .fixture_execution import execute as fixture_execute
                    result=fixture_execute(self,j)
                self._inputs(j['payload']['spec'],j['payload']['approval'])
                self.finish(jid,worker,fence,result=result)
            except ValueError:
                try:self.finish(jid,worker,fence,state='INCONCLUSIVE',result={'verdict':'INCONCLUSIVE','usage':None,'reason':'preflight_or_authority_check_failed'})
                except ValueError:pass  # Expired/lost owner: recover() seals it.
                self.recover()
            return self.get(jid)
