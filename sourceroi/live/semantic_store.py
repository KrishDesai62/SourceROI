"""Authenticated immutable claim judgments, separate from maintenance approval.

Reviewer login is not external independence. No endpoint accepts a client claim
of verified independence; this phase records it as unverified. Fixtures can never
promote a production release to ACCEPT.
"""
import json
import secrets
from .data_ci import digest

class SemanticStore:
    def __init__(self,jobs):
        self.jobs=jobs;self.store=jobs.store
        with self.store.connect() as c:c.execute('''CREATE TABLE IF NOT EXISTS semantic_judgments(id TEXT PRIMARY KEY,job TEXT NOT NULL,task TEXT NOT NULL,reviewer TEXT NOT NULL,revision INTEGER NOT NULL,binding TEXT NOT NULL,body TEXT NOT NULL,UNIQUE(job,task,reviewer))''')

    def packet(self,jid,task_id):
        j=self.jobs.get(jid)
        if not j or j['state']!='COMPLETED' or not j['result'] or j['result'].get('kind')!='fixture_release':raise ValueError('Job has no complete evaluated claim to review')
        self.jobs._inputs(j['payload']['spec'],j['payload']['approval'])
        release=j['result']['release'];row=next((r for r in release['tasks'] if r['task_id']==task_id),None)
        if row is None:raise ValueError('Unknown evaluated task')
        sample=row['grounding_checks']['sample']
        body={'job':jid,'task':task_id,'sample':sample,'policy':release['release_policy'],
              'source_versions':j['payload']['identity']['versions'],'result_identity':digest(j['result'])}
        return {**body,'binding':digest(body),'independence_verified_externally':False,'fixture_only':True}

    def allowed(self,j,actor):
        assigned=j['payload']['approval'].get('authenticated_identity',{}).get('id')
        return actor['role']=='admin' or actor['role']=='reviewer' and actor['id']==assigned

    def put(self,jid,task_id,actor,*,binding,decision,claims,rationale,authorization_basis,dimensions):
        j=self.jobs.get(jid)
        if not j or not self.allowed(j,actor):raise ValueError('Reviewer is not assigned to this job')
        packet=self.packet(jid,task_id)
        if packet['binding']!=binding:raise ValueError('Stale or substituted semantic-review binding')
        if decision not in ('supported','unsupported','contradicted','uncertain','applicability_failure'):raise ValueError('Invalid semantic decision')
        if not isinstance(rationale,str) or not rationale.strip() or not isinstance(authorization_basis,str) or not authorization_basis.strip():raise ValueError('Actual review rationale and authorization basis required')
        if not isinstance(claims,list):raise ValueError('Claims must be explicit reviewer input')
        fields={'semantic_correctness','citation_correctness','scope_appropriate','uses_outdated_fact'}
        if not isinstance(dimensions,dict) or set(dimensions)!=fields or any(v is not None and type(v) is not bool for v in dimensions.values()):raise ValueError('Every semantic dimension must be explicitly judged or unknown')
        if decision in ('supported','unsupported','contradicted'):
            from .grounding import score_review,evidence_key
            sample=packet['sample']
            if not claims or any(c.get('verdict')!=decision for c in claims):raise ValueError('Claim judgments must match declared decision')
            score_review(sample['question'],sample['answer'],sample['context'],sample['citations'],{evidence_key(sample['question'],sample['answer'],sample['context']):{'status':'complete','reviewer':actor['name'],'claims':claims}})
        if decision=='supported' and (any(type(v) is not bool for v in dimensions.values()) or not dimensions['semantic_correctness'] or not dimensions['citation_correctness'] or not dimensions['scope_appropriate'] or dimensions['uses_outdated_fact']):raise ValueError('Supported review conflicts with incomplete/negative dimensions')
        with self.store.connect() as c:
            user=c.execute('SELECT * FROM users WHERE id=? AND enabled=1',(actor['id'],)).fetchone()
            if not user or user['role'] not in ('reviewer','admin'):raise ValueError('Live reviewer permission required')
            rev=c.execute('SELECT revision FROM identity_revisions WHERE user_id=?',(actor['id'],)).fetchone();revision=rev[0] if rev else 0
            if c.execute('SELECT 1 FROM semantic_judgments WHERE job=? AND task=? AND reviewer=?',(jid,task_id,actor['id'])).fetchone():raise ValueError('Immutable semantic judgment already recorded; no replay/overwrite')
            body={'job':jid,'task':task_id,'binding':binding,'reviewer':{'id':actor['id'],'name':user['name'],'role':user['role']},
                  'decision':decision,'claims':claims,'dimensions':dimensions,'rationale':rationale,'authorization_basis':authorization_basis,
                  'independence_verified_externally':False,'independence_basis':'Not established by login or reviewer assertion',
                  'fixture_only':True,'created_at':self.store.clock(),'nonce':secrets.token_hex(16)}
            record={**body,'id':digest(body)}
            c.execute('INSERT INTO semantic_judgments VALUES (?,?,?,?,?,?,?)',(record['id'],jid,task_id,actor['id'],revision,binding,json.dumps(record)))
            c.execute('INSERT INTO audit(at,event,actor,status) VALUES (?,?,?,?)',(self.store.clock(),'semantic_judgment_recorded',actor['id'],201))
        return record

    def assess(self,jid):
        j=self.jobs.get(jid)
        if not j or j['state']!='COMPLETED' or not j['result']:return {'verdict':'INCONCLUSIVE','reason':'Execution incomplete'}
        if j['result'].get('kind')!='fixture_release':return {'verdict':'INCONCLUSIVE','reason':'No evaluated fixture release'}
        from .fixture_execution import reconcile
        try:current=reconcile(self.jobs,j)
        except (ValueError,KeyError,TypeError):return {'verdict':'INCONCLUSIVE','reason':'Fixture reconciliation invalid'}
        if current!=j['result'].get('reconciliation'):return {'verdict':'INCONCLUSIVE','reason':'Fixture reconciliation seal changed'}
        with self.store.connect() as c:
            attempts=c.execute('SELECT state FROM job_attempts WHERE job=?',(jid,)).fetchall()
            if any(r[0]!='COMPLETED' for r in attempts):return {'verdict':'INCONCLUSIVE','reason':'Provider fixture unreconciled'}
            records=c.execute('SELECT s.*,u.role,u.enabled FROM semantic_judgments s JOIN users u ON u.id=s.reviewer WHERE s.job=?',(jid,)).fetchall()
        valid=[];stale=0
        for r in records:
            try:current=self.packet(jid,r['task'])
            except ValueError:return {'verdict':'INCONCLUSIVE','reason':'Source/result identity changed'}
            with self.store.connect() as c:rev=c.execute('SELECT revision FROM identity_revisions WHERE user_id=?',(r['reviewer'],)).fetchone()
            if not r['enabled'] or r['role'] not in ('reviewer','admin') or (rev[0] if rev else 0)!=r['revision'] or r['binding']!=current['binding']:stale+=1;continue
            valid.append(json.loads(r['body']))
        release=j['result']['release']
        negative=any(r['decision'] in ('unsupported','contradicted','applicability_failure') for r in valid)
        verdict='BLOCK' if release['verdict']=='BLOCK' or negative else 'REVIEW'
        return {'verdict':verdict,'valid_judgments':len(valid),'stale_judgments':stale,'fixture_only':True,
                'independence_verified_externally':False,'reason':'Fixture execution and unverified reviewer independence cannot authorize ACCEPT'}
