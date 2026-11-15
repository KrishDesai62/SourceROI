"""Workspace-bound local identity store. Trusted OS administrator is the root of trust.

No network identity provider, public TLS termination, or hostile-host isolation is
claimed. The store contains password/session hashes, never plaintext credentials.
"""
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import time

ROLES={'viewer','operator','reviewer','admin'}
COOKIE='sourceroi_session'


def hashed(value):return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password,salt):
    return hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()


class SecurityStore:
    def __init__(self,workspace,*,initialize=False,migrate=False,clock=time.time,ttl=3600):
        from .config import secure_path
        self.root=Path(workspace).expanduser().resolve();self.clock=clock
        if not 60<=ttl<=3600:raise ValueError('Session TTL must be 60..3600 seconds')
        self.ttl=ttl
        if any(p.is_symlink() for p in (self.root/'.sourceroi',self.root/'.sourceroi/security')):
            raise ValueError('Identity directory symlinks forbidden')
        folder=secure_path(self.root,'.sourceroi/security',must_exist=False)
        self.path=folder/'identity.sqlite3'
        if initialize:folder.mkdir(parents=True,mode=0o700,exist_ok=True)
        if folder.is_symlink() or self.path.is_symlink():raise ValueError('Identity store symlinks forbidden')
        if initialize and not self.path.exists():
            fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        if not self.path.is_file():raise ValueError('Initialize the identity store before authenticated startup')
        for path in (folder,self.path):
            info=path.stat()
            if info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)&0o077:raise ValueError('Identity store requires owner-only permissions')
        if self.path.stat().st_nlink!=1:raise ValueError('Identity store hardlinks forbidden')
        self.binding=hashed(str(self.root))
        with self.connect() as conn:
            if initialize:
                conn.executescript('''
                CREATE TABLE IF NOT EXISTS metadata (version INTEGER NOT NULL,workspace TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY,name TEXT UNIQUE NOT NULL,salt TEXT NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL,enabled INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY,user_id TEXT NOT NULL,csrf TEXT NOT NULL,expires REAL NOT NULL,revoked INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS failures (bucket TEXT NOT NULL,at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS plans (id TEXT PRIMARY KEY,body TEXT NOT NULL,snapshot TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS approvals (id TEXT PRIMARY KEY,spec TEXT NOT NULL,actor TEXT NOT NULL,expires REAL NOT NULL,used INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY,at REAL NOT NULL,event TEXT NOT NULL,actor TEXT,status INTEGER NOT NULL,request_id TEXT);
                ''')
                if not conn.execute('SELECT 1 FROM metadata').fetchone():conn.execute('INSERT INTO metadata VALUES (?,?)',(2,self.binding))
            row=conn.execute('SELECT version,workspace FROM metadata').fetchone()
            if not row or row['workspace']!=self.binding or row['version'] not in (1,2):raise ValueError('Incompatible identity store or wrong workspace; reprovision identities after restore')
            if row['version']==1:
                if not migrate:raise ValueError('Identity schema 1 requires explicit quiesced auth-migrate; no unauthenticated fallback')
                tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if 'job_schema' in tables and conn.execute('SELECT version FROM job_schema').fetchone()[0]!=1:raise ValueError('Unsupported job schema; migration refused')
                conn.execute('CREATE TABLE IF NOT EXISTS approval_revocations(id TEXT PRIMARY KEY)')
                conn.execute('CREATE TABLE IF NOT EXISTS identity_revisions(user_id TEXT PRIMARY KEY,revision INTEGER NOT NULL)')
                conn.execute('UPDATE sessions SET revoked=1')
                conn.execute('INSERT OR IGNORE INTO approval_revocations SELECT id FROM approvals')
                conn.execute('UPDATE approvals SET used=1')
                for user in conn.execute('SELECT id FROM users').fetchall():
                    conn.execute('INSERT INTO identity_revisions VALUES (?,1) ON CONFLICT(user_id) DO UPDATE SET revision=revision+1',(user[0],))
                if 'jobs' in tables:
                    for job in conn.execute("SELECT id,fence FROM jobs WHERE state NOT IN ('COMPLETED','FAILED','CANCELLED','INCONCLUSIVE')").fetchall():
                        conn.execute("UPDATE jobs SET state='INCONCLUSIVE',reason='identity_upgrade_requires_reconciliation',fence=fence+1,lease=0,updated=? WHERE id=?",(self.clock(),job['id']))
                        conn.execute('INSERT INTO job_events(job,at,state,reason,fence) VALUES (?,?,?,?,?)',(job['id'],self.clock(),'INCONCLUSIVE','identity_upgrade_requires_reconciliation',job['fence']+1))
                if 'job_attempts' in tables:conn.execute("UPDATE job_attempts SET state='UNKNOWN',updated=? WHERE state IN ('RESERVED','DISPATCHED')",(self.clock(),))
                conn.execute('UPDATE metadata SET version=2')
                conn.execute('INSERT INTO audit(at,event,actor,status) VALUES (?,?,?,?)',(self.clock(),'identity_schema_upgraded',None,200))
            # Additive migration: consumed and revoked are distinct once receipts
            # are attached to durable jobs. Never infer live authority from used=1.
            conn.execute('CREATE TABLE IF NOT EXISTS approval_revocations(id TEXT PRIMARY KEY)')
            conn.execute('CREATE TABLE IF NOT EXISTS identity_revisions(user_id TEXT PRIMARY KEY, revision INTEGER NOT NULL)')

    @contextmanager
    def connect(self):
        conn=sqlite3.connect(self.path,timeout=5)
        conn.row_factory=sqlite3.Row
        try:
            conn.execute('PRAGMA journal_mode=DELETE')
            conn.execute('BEGIN IMMEDIATE')
            yield conn;conn.commit()
        except BaseException:conn.rollback();raise
        finally:conn.close()

    def audit(self,event,actor=None,status=200,request_id=None):
        # Callers supply fixed event names, not URLs, bodies, passwords or tokens.
        with self.connect() as conn:conn.execute('INSERT INTO audit(at,event,actor,status,request_id) VALUES (?,?,?,?,?)',(self.clock(),event,actor,status,request_id))

    def add_user(self,name,password,role):
        if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,64}',name) or role not in ROLES:raise ValueError('Invalid username or role')
        if not isinstance(password,str) or not 16<=len(password)<=1024:raise ValueError('Password must contain 16..1024 characters')
        salt=secrets.token_hex(16);encoded=password_hash(password,salt)
        with self.connect() as conn:
            if conn.execute('SELECT 1 FROM users WHERE name=?',(name,)).fetchone():raise ValueError('User already exists; use set_role or reset_password explicitly')
            conn.execute('INSERT INTO users VALUES (?,?,?,?,?,1)',(secrets.token_hex(16),name,salt,encoded,role))
        self.audit('identity_created')

    def set_role(self,name,role):
        if role not in ROLES:raise ValueError('Invalid role')
        with self.connect() as conn:
            row=conn.execute('SELECT id FROM users WHERE name=?',(name,)).fetchone()
            if not row:raise ValueError('Unknown user')
            conn.execute('UPDATE users SET role=? WHERE id=?',(role,row['id']))
            self._revoke(conn,row['id'])
        self.audit('role_changed',row['id'])

    def reset_password(self,name,password):
        if not 16<=len(password)<=1024:raise ValueError('Password must contain 16..1024 characters')
        salt=secrets.token_hex(16);encoded=password_hash(password,salt)
        with self.connect() as conn:
            row=conn.execute('SELECT id FROM users WHERE name=?',(name,)).fetchone()
            if not row:raise ValueError('Unknown user')
            conn.execute('UPDATE users SET password=?,salt=? WHERE id=?',(encoded,salt,row['id']));self._revoke(conn,row['id'])
        self.audit('credential_reset',row['id'])

    def _revoke(self,conn,uid):
        conn.execute('INSERT INTO identity_revisions VALUES (?,1) ON CONFLICT(user_id) DO UPDATE SET revision=revision+1',(uid,))
        conn.execute('UPDATE sessions SET revoked=1 WHERE user_id=?',(uid,))
        conn.execute('INSERT OR IGNORE INTO approval_revocations SELECT id FROM approvals WHERE actor=?',(uid,))
        conn.execute('UPDATE approvals SET used=1 WHERE actor=?',(uid,))

    def revoke_user(self,name):
        with self.connect() as conn:
            row=conn.execute('SELECT id FROM users WHERE name=?',(name,)).fetchone()
            if not row:raise ValueError('Unknown user')
            conn.execute('UPDATE users SET enabled=0 WHERE id=?',(row['id'],));self._revoke(conn,row['id'])
        self.audit('identity_disabled',row['id'])

    def login(self,name,password):
        if not isinstance(name,str) or not isinstance(password,str) or len(name)>64 or len(password)>1024:raise PermissionError('Invalid credentials')
        now=self.clock();buckets=[hashed('user:'+name),'local-global']
        # Bound concurrent password hashing under one serialized transaction.
        with self.connect() as conn:
            conn.execute('DELETE FROM failures WHERE at<?',(now-900,))
            if any(conn.execute('SELECT COUNT(*) FROM failures WHERE bucket=?',(b,)).fetchone()[0]>=limit for b,limit in zip(buckets,(5,20))):raise PermissionError('Login temporarily unavailable')
            row=conn.execute('SELECT * FROM users WHERE name=?',(name,)).fetchone()
            candidate=password_hash(password,row['salt'] if row else '00'*16)
            valid=row and row['enabled'] and hmac.compare_digest(row['password'],candidate)
            if not valid:
                conn.executemany('INSERT INTO failures VALUES (?,?)',[(b,now) for b in buckets])
            else:
                token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
                conn.execute('INSERT INTO sessions VALUES (?,?,?,?,0)',(hashed(token),row['id'],hashed(csrf),now+self.ttl))
        if not valid:self.audit('login_denied',status=401);raise PermissionError('Invalid credentials')
        self.audit('login_success',row['id'])
        return {'token':token,'csrf':csrf,'expires_at':now+self.ttl,'user':{'id':row['id'],'name':row['name'],'role':row['role']}}

    def authenticate(self,token):
        if not token or len(token)>200:return None
        with self.connect() as conn:
            row=conn.execute('SELECT u.id,u.name,u.role,s.csrf,s.token,s.expires FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.revoked=0 AND s.expires>? AND u.enabled=1',(hashed(token),self.clock())).fetchone()
            return dict(row) if row else None

    def logout(self,token):
        with self.connect() as conn:conn.execute('UPDATE sessions SET revoked=1 WHERE token=?',(hashed(token),))

    def register_plan(self,spec,snapshot):
        from .assurance import validate_spec
        validate_spec(spec)
        with self.connect() as conn:conn.execute('INSERT OR IGNORE INTO plans VALUES (?,?,?)',(spec['id'],json.dumps(spec,sort_keys=True),snapshot))

    def registered_plan(self,spec):
        with self.connect() as conn:row=conn.execute('SELECT body,snapshot FROM plans WHERE id=?',(spec['id'],)).fetchone()
        if not row or json.loads(row['body'])!=spec:raise ValueError('Review requires the exact server-registered plan')
        return row['snapshot']

    def bind_approval(self,approval,actor):
        from .data_ci import digest
        result={**approval,'authenticated_identity':{'id':actor['id'],'name':actor['name'],'role':actor['role'],'workspace':self.binding},'authority_basis':{'maintenance':'authenticated local role','source_owner_delegation':'UNVERIFIED','external_independence':'UNVERIFIED','generation_permission':False,'release_permission':False}}
        result['id']=digest({k:v for k,v in result.items() if k!='id'})
        with self.connect() as conn:conn.execute('INSERT INTO approvals VALUES (?,?,?,?,0)',(result['id'],result['spec_id'],actor['id'],self.clock()+3600))
        self.audit('approval_recorded',actor['id']);return result

    def consume_approval(self,approval,spec):
        from .assurance import validate_review,validate_release_inputs
        from .config import read_config,secure_path
        validate_review(spec,approval)
        snapshot=self.registered_plan(spec)
        validate_release_inputs(read_config(secure_path(self.root,'.sourceroi/snapshots/'+snapshot)),read_config(self.root),spec,approval)
        with self.connect() as conn:
            row=conn.execute('SELECT a.*,u.role,u.enabled FROM approvals a JOIN users u ON u.id=a.actor WHERE a.id=? AND a.spec=?',(approval['id'],spec['id'])).fetchone()
            revoked=conn.execute('SELECT 1 FROM approval_revocations WHERE id=?',(approval['id'],)).fetchone()
            if not row or revoked or row['used'] or row['expires']<=self.clock() or not row['enabled'] or row['role'] not in ('reviewer','admin'):raise ValueError('Approval missing, expired, revoked or already consumed')
            conn.execute('UPDATE approvals SET used=1 WHERE id=?',(approval['id'],))
        self.audit('approval_consumed',row['actor'])


class IdentityBoundary:
    """Authentication/role checks before handlers, including synchronous workers.

    This first staged target intentionally disables generation routes. Existing
    local CLI execution is outside this HTTP boundary and requires OS trust.
    """
    GENERATION={'/api/v2/runs','/api/v2/knowledge/release','/api/v2/data-ci','/api/v2/optimize','/api/v2/studies','/api/v2/reliability-studies'}

    def __init__(self,app,store):self.app=app;self.store=store

    async def __call__(self,scope,receive,send):
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        if scope['type']!='http':return await self.app(scope,receive,send)
        import ipaddress
        peer=(scope.get('client') or ('',))[0]
        try:local=ipaddress.ip_address(peer).is_loopback
        except ValueError:local=peer=='testclient'
        if not local:
            return await JSONResponse({'detail':'Authenticated target requires a direct loopback connection; proxies unsupported'},403)(scope,receive,send)
        path=scope['path'];method=scope['method'];state=scope.setdefault('state',{})
        request=Request(scope);rid=state.get('request_id')
        public=method=='GET' and path in ('/','/app.js','/styles.css','/api/v2/health','/api/v2/auth/mode') or method=='POST' and path=='/api/v2/auth/login'
        if public:return await self.app(scope,receive,send)
        async def refuse(status,detail,event):
            self.store.audit(event,status=status,request_id=rid)
            return await JSONResponse({'detail':detail},status)(scope,receive,send)
        if len(request.headers.getlist('authorization'))>1 or len(request.headers.getlist('cookie'))>1:
            return await refuse(400,'Ambiguous authentication headers','ambiguous_credentials')
        header=request.headers.get('authorization');cookie=request.cookies.get(COOKIE)
        if header and cookie:return await refuse(400,'Use one session transport','ambiguous_credentials')
        token=header[7:] if header and header.startswith('Bearer ') else cookie if not header else None
        try:actor=self.store.authenticate(token)
        except sqlite3.Error:return await JSONResponse({'detail':'Identity storage unavailable'},503)(scope,receive,send)
        if not actor:return await refuse(401,'Authentication required','unauthenticated')
        if method not in ('GET','HEAD','OPTIONS') and cookie:
            csrf=request.headers.get('x-csrf-token','')
            if not request.headers.get('origin') or not hmac.compare_digest(hashed(csrf),actor['csrf']):return await refuse(403,'Same-origin CSRF token required','csrf_denied')
        review=(path=='/api/v2/knowledge/review' or path.endswith('/semantic-reviews')) and method=='POST'
        mutation=method not in ('GET','HEAD','OPTIONS') and path!='/api/v2/auth/logout'
        allowed=('reviewer','admin') if review else ('operator','admin') if mutation else tuple(ROLES)
        if actor['role'] not in allowed:return await refuse(403,'Role does not permit this operation','role_denied')
        if method=='POST' and path in self.GENERATION:
            return await refuse(403,'Authenticated execution remains disabled pending durable jobs, parser isolation and separate execution authorization','execution_disabled')
        state['principal']=actor;state['session_token']=token
        async def audited(message):
            if message['type']=='http.response.start':
                self.store.audit('review_request' if review else 'write_request' if mutation else 'read_request',actor['id'],message['status'],rid)
            await send(message)
        await self.app(scope,receive,audited)
